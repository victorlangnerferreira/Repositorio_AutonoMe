# AutonoMe

App instalável e responsivo para conectar profissionais autônomos e clientes. A interface foi construída a partir das telas exportadas do Figma e mantém o foco nas áreas de serviço, contratação, mensagens, notificações, favoritos e suporte.

## Instalar no celular

Publique os arquivos em um endereço HTTPS e abra-o no celular:

- **Android:** no Chrome, abra o menu e toque em **Instalar app** ou **Adicionar à tela inicial**.
- **iPhone/iPad:** no Safari, toque em **Compartilhar** e depois em **Adicionar à Tela de Início**.

O AutonoMe abre em modo de app e guarda os arquivos da interface para que ela possa ser iniciada sem conexão depois da primeira visita. Em computadores ou quando o navegador não oferece instalação, a experiência continua disponível como site.

## Executar localmente

O backend do AutonoMe serve a interface e a API no mesmo endereço. Configure as variáveis SMTP do seu provedor de e-mail e uma chave secreta em seu ambiente; não publique nem compartilhe esses valores:

```powershell
$env:APP_SECRET = (py -c "import secrets; print(secrets.token_urlsafe(48))")
$env:SMTP_HOST = "<servidor-smtp>"
$env:SMTP_PORT = "587"
$env:SMTP_USERNAME = "<usuario-smtp>"
$env:SMTP_PASSWORD = "<senha-de-aplicativo>"
$env:SMTP_FROM = "<email-remetente-verificado>"
py server.py
```

Abra `http://127.0.0.1:8000`. A primeira inicialização cria `data/autonome.sqlite3` com tabelas para contas ativas, códigos temporários, sessões e usuários desativados. A configuração de envio de e-mail é obrigatória para cadastro ou desativação; se faltar, o servidor informa o erro e não simula o envio do código. Em produção, use HTTPS, defina `APP_ENV=production` e `COOKIE_SECURE=true`, além de uma chave `APP_SECRET` persistente e protegida. O código tem seis letras/números, vence em 10 minutos, permite até cinco tentativas e pode ser reenviado após 1 minuto. O CPF é validado no servidor, mas não é armazenado nem consultado na Receita Federal.

Para produção, configure também `AUTONOME_HOST=0.0.0.0` atrás de um proxy HTTPS, defina `AUTONOME_DB_PATH` para um volume persistente e mantenha `APP_SECRET` estável entre reinicializações. Para testar os endpoints sem enviar e-mails, execute `py -m unittest discover -s tests -v`.

Sem backend, abrir `index.html` ou publicar somente os arquivos estáticos não permite login, cadastro verificado ou desativação de conta. O modo offline do PWA cobre apenas os arquivos da interface; a API e o envio de e-mail precisam estar hospedados e acessíveis.

## APK Android conectado ao servidor

O APK de desenvolvimento sem configuração abre uma cópia local da interface e não consegue acessar a API. Para autenticação funcionar, primeiro publique **o backend e a interface juntos no mesmo endereço HTTPS**, configure as variáveis de produção e SMTP acima e confirme que o endereço abre o AutonoMe no celular. Em seguida, gere o APK apontando para esse endereço:

```powershell
gradle -p android assembleDebug "-PautonomeAppUrl=https://SEU-DOMINIO/"
```

O projeto Android requer JDK 17, Android SDK 34 e Gradle 8.7. O APK conectado será criado em `android/app/build/outputs/apk/debug/app-debug.apk` e abrirá o endereço informado dentro do app. Não compartilhe o APK até substituir `https://SEU-DOMINIO/` por um domínio HTTPS ativo. O endereço é validado no build; URLs HTTP não são aceitas. Sem `autonomeAppUrl`, a interface local continua disponível para pré-visualização, mas cadastro, login, verificação por e-mail e desativação informam que o servidor precisa ser conectado.

## Publicar no Render

Os arquivos `Dockerfile` e `render.yaml` configuram um serviço gratuito para **testes iniciais**, sem cobrança automática de compute. Neste plano o servidor pode dormir após 15 minutos sem uso, o banco SQLite fica em armazenamento temporário e conexões SMTP de saída são bloqueadas. Assim, a interface e a API podem abrir, mas o cadastro e a desativação por e-mail não funcionam nesse plano. Não use esta configuração para dados importantes. Para preservar contas será necessário migrar para um plano que aceite disco persistente, montar o disco em `/data` e definir `AUTONOME_DB_PATH=/data/autonome.sqlite3`; serviços pagos podem gerar cobranças. Para publicar:

1. Envie este repositório para o GitHub e confirme que a branch a publicar contém `Dockerfile` e `render.yaml`.
2. Crie ou entre na sua conta em [dashboard.render.com](https://dashboard.render.com), escolha **New → Blueprint**, conecte o GitHub e selecione o repositório/branch.
3. Revise e confirme o Blueprint `render.yaml`. Ele configura o serviço gratuito de teste e gera `APP_SECRET` automaticamente.
4. As variáveis SMTP aparecem no Blueprint, mas só funcionam em um serviço/hospedagem que permita conexões SMTP de saída. Para uma hospedagem compatível, preencha no painel do serviço:

   | Variável | Valor |
   | --- | --- |
   | `APP_ENV` | `production` |
   | `APP_SECRET` | chave aleatória privada com pelo menos 32 caracteres |
   | `COOKIE_SECURE` | `true` |
   | `AUTONOME_DB_PATH` | `/data/autonome.sqlite3` |
   | `SMTP_HOST` | servidor SMTP do provedor de e-mail |
   | `SMTP_PORT` | `587` |
   | `SMTP_USERNAME` | usuário SMTP |
   | `SMTP_PASSWORD` | senha de aplicativo SMTP |
   | `SMTP_FROM` | endereço remetente verificado no provedor |

5. Gere um domínio público HTTPS em **Settings → Networking → Generate Domain**. Espere o deploy ficar saudável, abra esse endereço no celular e teste o envio de código por e-mail. No plano Free, o endpoint de cadastro retornará uma mensagem explicando que o serviço SMTP está indisponível.
6. Gere o APK com o endereço HTTPS do domínio Render usando o comando da seção anterior. O app e o backend ficam no mesmo domínio, necessário para que o cookie de sessão funcione corretamente.

O serviço gratuito pode ficar temporariamente indisponível ao acordar e não preserva os dados locais entre reinicializações. Este backend atualmente envia e-mails somente por SMTP; um provedor que ofereça apenas API HTTPS ainda não é compatível. Nunca envie `APP_SECRET`, senha SMTP ou códigos de verificação pelo chat; `APP_SECRET` é gerado pelo Render e as credenciais SMTP devem ser preenchidas apenas no painel **Environment** do serviço. O APK atual não ganha conectividade retroativamente: é necessário gerar e instalar outro APK depois de ter o domínio publicado.

### Configurar envio com Gmail em hospedagem compatível com SMTP

O envio por `smtp.gmail.com:587` **não funciona no plano Free do Render**, mesmo que as variáveis estejam preenchidas. Em um plano/hospedagem que permita SMTP, abra o serviço no Render e vá a **Environment → Edit**. Configure `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USERNAME` com seu endereço Gmail, `SMTP_FROM` com o mesmo endereço e `SMTP_PASSWORD` com uma **senha de app Google** (não a senha normal da conta). A senha de app é criada em [Segurança da Conta Google → Senhas de app](https://myaccount.google.com/apppasswords); a verificação em duas etapas precisa estar ativa. Salve e aguarde o deploy ficar **Live**. Não compartilhe a senha de app no chat nem no GitHub. Se usar outro provedor, obtenha dele o host, a porta, o usuário, a senha SMTP e o remetente autorizado.

Se quiser continuar usando o plano Free do Render, será necessário integrar um provedor de envio por API HTTPS; isso ainda exige escolher um provedor e configurar um remetente autorizado, e não é suportado pelo backend atual. Não adianta adicionar uma chave de API de e-mail ao Render até essa integração existir.

## Fluxos incluídos

- Escolha do perfil **contratante**, **profissional contratado** ou dos dois; a opção pode ser alterada em Perfil ou Configurações
- Uma pessoa profissional de demonstração por categoria durante os testes: Construção Civil, Trabalho Doméstico, Entregas e Logística, Beleza e Bem-estar, Alimentação, Reparos e Assistência, Transporte, Entretenimento e Eventos, Aulas e Serviços Digitais, Pets e Animais, Serviços Pessoais e Outros serviços
- Busca de serviços e perfis de profissionais; a categoria "Outros serviços" aceita trabalhos que ainda não aparecem na lista
- Publicação e gerenciamento dos próprios anúncios e saída da conta pelo menu lateral
- Cadastro com máscara automática de CPF e celular, validação dos dígitos verificadores e do formato de celular brasileiro
- Confirmação de cadastro e desativação por código aleatório de seis caracteres enviado por e-mail; contas desativadas são movidas da tabela `users` para `disabled_users`
- Sessões autenticadas por cookie HttpOnly e senha protegida com PBKDF2; as configurações de SMTP e hospedagem são fornecidas pelo operador
- Ao tocar em uma profissão, abre-se uma tela dedicada com os profissionais correspondentes, busca e navegação de retorno
- Escolha de data e horário, acompanhamento de pedidos e cancelamento de contratações
- Um profissional com pedido ativo deixa de aparecer nos resultados e volta a ficar disponível quando a contratação é cancelada
- Consulta de contratos, conversas e notificações sem mensagens ou pedidos de demonstração apresentados como reais
- Favoritos, configurações, avaliação e formulários de contato e ajuda

Dados de pedidos, favoritos e anúncios continuam locais ao dispositivo; o backend armazena contas e usuários desativados, mas não sincroniza esses dados do app. A validação do CPF verifica formato e dígitos, mas não consulta situação cadastral na Receita Federal. O CPF não é armazenado. Os perfis de profissionais estão identificados como demonstração. A versão web pode ser instalada como PWA; o projeto também gera um APK Android de teste com WebView, ainda não publicado na Google Play.
