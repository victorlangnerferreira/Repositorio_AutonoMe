# AutonoMe

App instalável e responsivo para conectar profissionais autônomos e clientes. A interface foi construída a partir das telas exportadas do Figma e mantém o foco nas áreas de serviço, contratação, mensagens, notificações, favoritos e suporte.

## Instalar no celular

Publique os arquivos em um endereço HTTPS e abra-o no celular:

- **Android:** no Chrome, abra o menu e toque em **Instalar app** ou **Adicionar à tela inicial**.
- **iPhone/iPad:** no Safari, toque em **Compartilhar** e depois em **Adicionar à Tela de Início**.

O AutonoMe abre em modo de app e guarda os arquivos da interface para que ela possa ser iniciada sem conexão depois da primeira visita. Em computadores ou quando o navegador não oferece instalação, a experiência continua disponível como site.

## Executar localmente

O backend do AutonoMe serve a interface e a API no mesmo endereço. Para enviar códigos sem SMTP, configure uma chave de API do Brevo, um remetente verificado e uma chave secreta em seu ambiente; não publique nem compartilhe esses valores:

```powershell
$env:APP_SECRET = (py -c "import secrets; print(secrets.token_urlsafe(48))")
$env:BREVO_API_KEY = "<chave-api-brevo>"
$env:EMAIL_FROM = "<email-remetente-verificado-no-brevo>"
py server.py
```

Abra `http://127.0.0.1:8000`. A primeira inicialização cria `data/autonome.sqlite3` com tabelas para contas, anúncios profissionais, pedidos de contratação, códigos temporários, sessões e usuários desativados. Anúncios e pedidos são compartilhados entre as contas; a API mantém privados e-mail e telefone dos usuários. A configuração de envio de e-mail é obrigatória para cadastro ou desativação; se faltar, o servidor informa o erro e não simula o envio do código. Também é possível usar SMTP definindo `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` e `SMTP_FROM`. Em produção, use HTTPS, defina `APP_ENV=production` e `COOKIE_SECURE=true`, além de uma chave `APP_SECRET` persistente e protegida. O código tem seis letras/números, vence em 10 minutos, permite até cinco tentativas e pode ser reenviado após 1 minuto. O CPF é validado no servidor, mas não é armazenado nem consultado na Receita Federal.

Para produção, configure também `AUTONOME_HOST=0.0.0.0` atrás de um proxy HTTPS, defina `AUTONOME_DB_PATH` para um volume persistente e mantenha `APP_SECRET` estável entre reinicializações. Para testar os endpoints sem enviar e-mails, execute `py -m unittest discover -s tests -v`.

Sem backend, abrir `index.html` ou publicar somente os arquivos estáticos não permite login, cadastro verificado ou desativação de conta. O modo offline do PWA cobre apenas os arquivos da interface; a API e o envio de e-mail precisam estar hospedados e acessíveis.

## APK Android conectado ao servidor

O APK de desenvolvimento sem configuração abre uma cópia local da interface e não consegue acessar a API. Para autenticação funcionar, primeiro publique **o backend e a interface juntos no mesmo endereço HTTPS**, configure as variáveis de produção e e-mail acima e confirme que o endereço abre o AutonoMe no celular. Em seguida, gere o APK apontando para esse endereço:

```powershell
gradle -p android assembleDebug "-PautonomeAppUrl=https://SEU-DOMINIO/"
```

O projeto Android requer JDK 17, Android SDK 34 e Gradle 8.7. O APK conectado será criado em `android/app/build/outputs/apk/debug/app-debug.apk` e abrirá o endereço informado dentro do app. Não compartilhe o APK até substituir `https://SEU-DOMINIO/` por um domínio HTTPS ativo. O endereço é validado no build; URLs HTTP não são aceitas. Sem `autonomeAppUrl`, a interface local continua disponível para pré-visualização, mas cadastro, login, verificação por e-mail e desativação informam que o servidor precisa ser conectado.

## Publicar no Render

O serviço Free do Render é apenas para testes: depois de 15 minutos sem uso ele desliga e apaga arquivos locais, incluindo o banco SQLite. Isso explica por que uma conta pode desaparecer depois de fechar o app: fechar o app não apaga a conta, mas a hospedagem gratuita elimina o banco quando a instância dorme ou reinicia. O Free não permite disco persistente. O Postgres Free do Render também expira após 30 dias, portanto não serve como armazenamento definitivo.

O `render.yaml` agora configura o menor compute pago (`0.5c-512mb`) e um disco persistente de 1 GB em `/app/data`; o servidor grava o banco em `/app/data/autonome.sqlite3`. Isso mantém contas, perfis, serviços, contratos e conversas entre reinicializações e deploys. Sincronizar essa alteração no Render faz upgrade para um serviço pago e adiciona o custo mensal do disco; consulte os valores atuais em [Render Pricing](https://render.com/pricing#compute) e [Persistent Disks](https://render.com/docs/disks). **Não sincronize o Blueprint se não quiser contratar o plano pago.** O disco tem snapshots automáticos diários, mantidos por sete dias.

Antes de sincronizar o Blueprint, faça backup dos dados que ainda estiverem disponíveis no serviço Free: o primeiro deploy com o disco inicia `/app/data` vazio, e o banco temporário atual não é migrado automaticamente pelo Render. Esta versão não contém uma ferramenta de exportação/migração do SQLite remoto. Contas já apagadas quando a instância Free dormiu não podem ser recuperadas pelo app; se o banco atual ainda não estiver acessível, será necessário cadastrar novamente uma vez depois que o disco persistente estiver ativo. Após a migração, os novos cadastros ficarão no disco.

O backend envia e-mails pela API HTTPS do Brevo, que não depende de SMTP. Para ativar a configuração:

1. Envie este repositório para o GitHub e confirme que a branch a publicar contém `Dockerfile` e `render.yaml`.
2. Crie ou entre na sua conta em [dashboard.render.com](https://dashboard.render.com), escolha **New → Blueprint**, conecte o GitHub e selecione o repositório/branch.
3. Revise e sincronize o Blueprint `render.yaml`. Ele altera o compute para o plano pago, adiciona o disco de 1 GB e gera `APP_SECRET` automaticamente. A alteração pode gerar cobranças mensais.
4. No painel do serviço, abra **Environment → Edit** e configure o remetente do Brevo. O Blueprint deixa o segredo para preenchimento privado e oferece estas variáveis:

   | Variável | Valor |
   | --- | --- |
   | `APP_ENV` | `production` |
   | `APP_SECRET` | chave aleatória privada com pelo menos 32 caracteres |
   | `COOKIE_SECURE` | `true` |
   | `AUTONOME_DB_PATH` | `/app/data/autonome.sqlite3` |
   | `BREVO_API_KEY` | chave API criada no painel do Brevo (secreta) |
   | `EMAIL_FROM` | endereço verificado na área de remetentes do Brevo |
   | `EMAIL_FROM_NAME` | nome apresentado ao destinatário (opcional; padrão `AutonoMe`) |

   No [Brevo](https://www.brevo.com/), crie a conta e uma [API key](https://developers.brevo.com/docs/api-key-authentication). Adicione um remetente em [Settings → Senders](https://app.brevo.com/senders). Para testar, o Brevo pode verificar um endereço individual enviando um código para essa caixa de entrada. Autenticar um domínio próprio com os registros DNS do Brevo é recomendado para melhor entregabilidade; remetentes de domínios gratuitos como Gmail podem receber avisos e ter menor entregabilidade.

   As variáveis SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` e `SMTP_FROM`) são opcionais e servem como alternativa em hospedagens que permitem conexões SMTP de saída. O plano Free do Render bloqueia SMTP.

5. Gere um domínio público HTTPS em **Settings → Networking → Generate Domain**. Espere o deploy ficar saudável, abra esse endereço no celular e teste o envio de código por e-mail. Acompanhe o status do serviço e confirme que o disco está montado em `/app/data`.
6. Gere o APK com o endereço HTTPS do domínio Render usando o comando da seção anterior. O app e o backend ficam no mesmo domínio, necessário para que o cookie de sessão funcione corretamente.

Nunca envie `APP_SECRET`, chave do Brevo, senha SMTP ou códigos de verificação pelo chat; `APP_SECRET` é gerado pelo Render e os segredos devem ser preenchidos apenas no painel **Environment** do serviço. O APK atual não ganha conectividade retroativamente: é necessário gerar e instalar outro APK depois de ter o domínio publicado.

### Configurar envio com Gmail em hospedagem compatível com SMTP

O envio por `smtp.gmail.com:587` **não funciona no plano Free do Render**, mesmo que as variáveis estejam preenchidas. A integração Brevo por API HTTPS é a opção para este plano. Em outra hospedagem que permita SMTP, configure `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USERNAME` com seu endereço Gmail, `SMTP_FROM` com o mesmo endereço e `SMTP_PASSWORD` com uma **senha de app Google** (não a senha normal da conta). A senha de app é criada em [Segurança da Conta Google → Senhas de app](https://myaccount.google.com/apppasswords); a verificação em duas etapas precisa estar ativa. Nunca compartilhe a senha de app no chat nem no GitHub.


## Fluxos incluídos

- Escolha do perfil **contratante**, **profissional contratado** ou dos dois; a opção pode ser alterada em Perfil ou Configurações
- Categorias de serviços disponíveis para anúncios de profissionais reais: Construção Civil, Trabalho Doméstico, Entregas e Logística, Beleza e Bem-estar, Alimentação, Reparos e Assistência, Transporte, Entretenimento e Eventos, Aulas e Serviços Digitais, Pets e Animais, Serviços Pessoais e Outros serviços
- Busca de serviços e perfis de profissionais; a categoria "Outros serviços" aceita trabalhos que ainda não aparecem na lista
- Publicação, edição, descoberta e remoção de anúncios de trabalhadores reais, compartilhados com todas as contas
- Edição de nome, apresentação, localização e foto de perfil; fotos são redimensionadas e comprimidas no dispositivo antes do envio
- Cadastro com máscara automática de CPF e celular, validação dos dígitos verificadores e do formato de celular brasileiro
- Confirmação de cadastro e desativação por código aleatório de seis caracteres enviado por e-mail; contas desativadas são movidas da tabela `users` para `disabled_users`
- Sessões autenticadas por cookie HttpOnly de 30 dias e senha protegida com PBKDF2; sair do app encerra apenas a sessão, enquanto desativar a conta exige confirmação por e-mail
- Ao tocar em uma profissão, abre-se uma tela dedicada com os profissionais correspondentes, busca e navegação de retorno
- Cadastro de horários semanais por profissional; o contratante só pode solicitar os horários publicados e ainda livres
- Escolha de data e horário, endereço opcional do atendimento, mensagem ao profissional, acompanhamento dos pedidos e cancelamento de contratações
- O profissional pode aceitar ou recusar pedidos recebidos; cada anúncio aceita um pedido ativo por vez
- Consulta dos pedidos enviados e recebidos entre contas; e-mail e telefone não são expostos nos perfis públicos
- Notificações compartilhadas sobre pedidos, confirmações, recusas e cancelamentos, com opção de marcar como lida ou excluir
- Chat privado por contratação entre contratante e profissional, com atualização automática, indicador de mensagens não lidas e bloqueio de acesso a terceiros
- Anotações privadas por contratação, separadas por usuário e visíveis somente ao autor
- Identidade visual e ícones PWA/Android atualizados com o logo enviado
- Favoritos, configurações, avaliação e formulários de contato e ajuda

Perfis, fotos, anúncios, pedidos, mensagens, disponibilidade, favoritos, notificações e anotações ficam no banco SQLite do backend; preferências de aparência e permissões continuam locais ao dispositivo. No Render, configure e ative o disco persistente descrito acima antes de usar contas reais; SQLite em armazenamento efêmero perde os dados quando o serviço Free dorme ou reinicia. O chat e as anotações só estão disponíveis às duas contas relacionadas a uma contratação; as anotações de cada pessoa são privadas. Mensagens diretas fora de contratações e compartilhamento público de telefone/e-mail não estão disponíveis. A validação do CPF verifica formato e dígitos, mas não consulta situação cadastral na Receita Federal. O CPF não é armazenado. Não há perfis fictícios no catálogo. A versão web pode ser instalada como PWA pelo menu do navegador; o projeto também gera APKs Android de teste com WebView, ainda não publicado na Google Play.
