# Ligar a signature pad Wacom STU (SigCaptX)

Este guia é o passo a passo para o pad Wacom STU (ligado por **USB**) funcionar
na recolha de assinaturas da Nota de Saída / Nota de Entrega.

O código do lado da aplicação (`app/static/js/wacom_sigpad.js`,
`app/static/vendor/sigcaptx/wgssSigCaptX.js`, `config.py`) **já está pronto** —
o que falta é o software da Wacom instalado na máquina onde o pad está ligado
(o computador do técnico que recolhe a assinatura, não o servidor da app).

## Como funciona (arquitetura)

```
Browser (esta app)  →  https://localhost:9000  →  serviço STU-SigCaptX  →  USB  →  pad Wacom STU
                        (instalado nesta máquina)   (Device Control App)
```

O browser nunca fala com o pad diretamente — fala com um **serviço local**
instalado pela Wacom (`wgssSTU_Server.exe`), que arranca automaticamente ao
iniciar sessão no Windows e escuta por omissão em `https://localhost:9000`.
Sem esse serviço a app continua a funcionar — cai automaticamente para
assinatura no `<canvas>` (rato/touch/caneta genérica).

## 1. Descarregar o SDK/serviço da Wacom

1. Criar conta gratuita em a(Wacom ID).
2. Entrar no **Developer Dashboard** → **Downloads** → secção **Wacom Device
   Kit** → componente **STU SigCaptX** (parte do "STU SDK for Windows").
3. Vem num instalador `Wacom-SigCaptX-XX.exe` (ou os MSI/EXE separados do
   driver + serviço).

> Não é preciso pedir nada pago: a Wacom liberalizou a licença do SigCaptX —
> é **gratuita** para todas as funções, exceto encriptação de assinatura e
> formatação ISO (nenhuma das duas é usada por esta app). Essa licença
> "Lite" já vem configurada por omissão em `config.py`
> (`WACOM_SIGCAPTX_LICENCE`) — não precisa de nenhum passo extra aqui.

## 2. Instalar

1. Ligar o pad Wacom STU por USB **antes** de instalar (o instalador procura
   o dispositivo).
2. Ter os browsers que vão ser usados (Chrome/Edge) já instalados — o
   instalador do SigCaptX regista-se para eles.
3. Correr o instalador com as opções por omissão. Instala em
   `C:\Program Files (x86)\Common Files\WacomGSS`.
4. O instalador cria um **certificado raiz autoassinado** ("Wacom Localhost
   STU Certificate Authority") na Loja de Certificados do Windows, para o
   HTTPS em `localhost` ser confiável sem avisos no browser.
5. O serviço (`wgssSTU_Server.exe`) fica a arrancar automaticamente com o
   Windows.

## 3. Verificar que o serviço está a funcionar (antes de testar na app)

A Wacom inclui uma página de teste **`PortCheck.html`** (vem com o SDK/
amostras) — abrir essa página no mesmo browser confirma se o serviço e o
pad estão detetados, sem depender desta aplicação. Se o PortCheck não
detetar o serviço, o problema é a instalação da Wacom, não o código desta
app.

Alternativa rápida: no Gestor de Tarefas, confirmar que `wgssSTU_Server.exe`
está em execução.

## 4. Confirmar a porta

Por omissão o serviço fica em **9000** (registo do Windows, chave
`ServicePort`). Se durante a instalação ficou noutra porta, definir na app:

```
WACOM_SIGCAPTX_PORT=<porta usada pelo serviço>
```

no `.env` (variável opcional — só é preciso se não for 9000).

## 5. Testar nesta app

1. Reiniciar o servidor Flask (para ler a configuração atualizada).
2. Abrir uma nota que esteja à espera de uma assinatura recolhida no pad
   (Recebido / Segurança — ou Entregue Por).
3. Clicar em "Recolher assinatura" — o painel mostra o estado do pad:
   - **"A ligar ao pad Wacom…"** → a detetar o serviço.
   - **"Pad Wacom pronto…"** → tudo certo, pode assinar no pad.
   - **"Serviço Wacom indisponível"** → o `wgssSTU_Server.exe` não está a
     responder em `https://localhost:<porta>` — voltar ao passo 3 (usar o
     PortCheck) antes de mexer no código.
   - **"Licença Wacom em falta"** → confirmar que `WACOM_SIGCAPTX_LICENCE`
     está definida (já vem com um valor por omissão; só ficaria vazia se
     alguém tiver posto `WACOM_SIGCAPTX_LICENCE=` no `.env`).

## Notas

- Isto é só necessário na máquina onde o pad está ligado — não afeta quem
  assina "Entregue Por"/"Autorizado Por" no seu próprio computador sem pad
  (continuam a poder assinar no `<canvas>`, exceto se
  `SIGNATURE_PAD_REQUIRED=1` estiver definido, aí o pad passa a ser
  obrigatório).
- Se o modelo do pad for a cores (ex.: STU-540), pode também ser preciso o
  **STU Driver** da Wacom (ex.: `Wacom-STU-Driver-5.4.5.exe`) para a
  transferência de imagem funcionar bem.
