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

## Publicar no Render com recursos gratuitos

O `render.yaml` mantém o servidor no plano Free do Render. Esse plano não tem disco persistente: qualquer banco SQLite gravado localmente pode ser apagado quando o serviço dorme após 15 minutos sem tráfego, reinicia ou recebe um novo deploy. Por isso, fechar o app não exclui a conta, mas o armazenamento local do servidor gratuito pode desaparecer. O PostgreSQL Free oferecido pelo próprio Render também expira após 30 dias.

Para manter os dados usando apenas recursos gratuitos, o servidor aceita PostgreSQL externo pela variável `DATABASE_URL`; uma opção é o plano Free permanente do [Neon](https://neon.com/pricing), que inclui até 1 GB por projeto e suspende o compute após inatividade. Ele tem limites de uso e pode demorar alguns instantes para acordar. Sem `DATABASE_URL`, o servidor usa SQLite local e os dados continuam sujeitos à perda no Render Free.

1. No [Neon Console](https://console.neon.tech/), crie um projeto gratuito. Em **Connect**, selecione a branch, o banco, o usuário e a conexão agrupada (*pooled*); copie a string de conexão `DATABASE_URL`.
2. No [Render Dashboard](https://dashboard.render.com), abra o serviço **autonome → Environment → Edit** e adicione `DATABASE_URL` com a string do Neon. O valor contém senha: preencha-o somente no painel do Render, nunca no chat ou no GitHub.
3. Faça o deploy da branch que contém este `render.yaml`. O compute continua `free` e nenhum disco pago é criado. Quando `DATABASE_URL` estiver presente, o servidor cria as tabelas no PostgreSQL; sem essa variável, ele inicia em SQLite local.
4. Configure também `APP_ENV=production`, `COOKIE_SECURE=true` e um `APP_SECRET` aleatório e estável de pelo menos 32 caracteres. O Blueprint gera `APP_SECRET` automaticamente.
5. Para cadastro por e-mail, configure `BREVO_API_KEY` e `EMAIL_FROM` no mesmo painel. No [Brevo](https://www.brevo.com/), crie uma API key e verifique um remetente em **Settings → Senders**. Remetentes de domínios gratuitos, como Gmail, podem ter menor entregabilidade.
6. Gere um domínio HTTPS em **Settings → Networking → Generate Domain**, aguarde o deploy ficar saudável e teste o acesso pelo celular. O APK deve apontar para esse domínio para autenticar no mesmo servidor.

As tabelas do Neon começam vazias; o Render não copia automaticamente o SQLite existente para a nova base. Esta versão não contém ferramenta para exportar o banco remoto atual, e contas já apagadas quando o serviço dormiu não podem ser recuperadas. Se o banco atual ainda estiver disponível e contiver dados importantes, não faça novo deploy antes de decidir como preservá-los. Depois de conectar o Neon, talvez seja necessário criar a conta novamente uma vez.

O Free do Render continua tendo inicialização lenta após períodos sem uso e limites mensais; o Neon Free também tem cotas e escala para zero. Consulte os limites atuais nas páginas de [Render Free](https://render.com/docs/free) e [Neon Pricing](https://neon.com/pricing). A conexão SMTP de saída é bloqueada no plano Free do Render; use a API HTTPS do Brevo. Nunca envie `DATABASE_URL`, `APP_SECRET`, chave do Brevo, senha SMTP ou códigos de verificação pelo chat.

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

Perfis, fotos, anúncios, pedidos, mensagens, disponibilidade, favoritos, notificações e anotações ficam no PostgreSQL quando `DATABASE_URL` está configurada; sem ela, o backend usa SQLite local. Preferências de aparência e permissões continuam locais ao dispositivo. No Render Free, configure uma base PostgreSQL externa para evitar que o banco local desapareça ao dormir ou reiniciar. O chat e as anotações só estão disponíveis às duas contas relacionadas a uma contratação; as anotações de cada pessoa são privadas. Mensagens diretas fora de contratações e compartilhamento público de telefone/e-mail não estão disponíveis. A validação do CPF verifica formato e dígitos, mas não consulta situação cadastral na Receita Federal. O CPF não é armazenado. Não há perfis fictícios no catálogo. A versão web pode ser instalada como PWA pelo menu do navegador; o projeto também gera APKs Android de teste com WebView, ainda não publicado na Google Play.
