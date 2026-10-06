# Cópia automática das notas concluídas (OneDrive / SharePoint)

Quando uma nota fica **concluída** (assinatura «Recebido»), a plataforma envia o
PDF final para a nuvem, automaticamente — ao mesmo tempo que prepara o email
para o colaborador. Nada disto atrasa o técnico; se a nuvem falhar, a nota
conclui-se na mesma e a falha fica nos logs.

Organização dos ficheiros:

    Notas de Saída/2026/10/NS_000012-2026_REQ000006253074_Maria-Silva.pdf
    Notas de Entrega/2026/10/NE_000003-2026_REQ000006253080_Joao-Cossa.pdf

> Um **link de partilha** do OneDrive/SharePoint não serve: deixa pessoas abrir a
> pasta, mas não deixa uma aplicação gravar ficheiros. Por isso usamos um flow do
> Power Automate, que dá um **link (URL) próprio** onde a plataforma entrega o PDF.

---

## 1. Criar o flow no Power Automate (uma vez)

1. Power Automate → **Create** → **Instant cloud flow** → gatilho
   **"When an HTTP request is received"**.
2. Em **Request Body JSON Schema**, cole:

```json
{
  "type": "object",
  "properties": {
    "pasta": { "type": "string" },
    "nome_ficheiro": { "type": "string" },
    "conteudo_base64": { "type": "string" },
    "tipo": { "type": "string" },
    "numero": { "type": "string" },
    "referencia": { "type": "string" },
    "colaborador": { "type": "string" },
    "email_colaborador": { "type": "string" },
    "departamento": { "type": "string" },
    "tecnico": { "type": "string" },
    "data_conclusao": { "type": "string" }
  }
}
```

3. **+ New step** → **SharePoint: Create file** (ou **OneDrive for Business: Create file**):
   - **Site Address / Folder Path:** a pasta raiz que a equipa da Direção de
     Informática indicar, seguida de `/` e do campo dinâmico **pasta**.
     Ex.: `/Shared Documents/Backups Notas/` + `pasta`
   - **File Name:** campo dinâmico **nome_ficheiro**
   - **File Content:** expressão `base64ToBinary(triggerBody()?['conteudo_base64'])`
4. **+ New step** → **Response** → Status Code `202`.
5. **Save**. Volte ao primeiro passo e copie o **HTTP POST URL** — é este o link.

> O gatilho HTTP do Power Automate é um conector **Premium**: confirme com a
> equipa que a conta tem essa licença.

## 2. Colocar o link na plataforma (sem mexer no código)

O link funciona como uma password — **não o coloque no código nem no repositório**.

No GitLab: **Settings → CI/CD → Variables → Add variable**

| Key | Value | Opções |
|---|---|---|
| `BACKUP_MODE` | `webhook` | |
| `BACKUP_WEBHOOK_URL` | *(o HTTP POST URL do flow)* | **Masked**, **Protected** |

Depois faça um deploy normal (push para `sbmz-dev`). A partir daí, cada nota
concluída é copiada automaticamente.

## 3. Enviar as notas que já existem / repetir envios falhados

Na pipeline, botão manual **`backup-notas-dev`** → ▶. Envia todas as notas
concluídas (ou só a partir de uma data: variável `BACKUP_DESDE=2026-10-01`).
Pode correr-se mais do que uma vez: o ficheiro com o mesmo nome é substituído.

## Alternativa: pasta de rede (share drive)

Se o destino for uma pasta de rede do banco (`\\servidor\pasta`), o servidor
tem de a montar e o `docker-compose.yml` tem de a ligar ao container (volume).
Depois: `BACKUP_MODE=pasta` e `BACKUP_PASTA=/caminho/dentro/do/container`.

## Verificar

- Logs da aplicação (Loki): `Backup OK (webhook): Notas de Saída/2026/10/...`
- Falhas: `Backup falhou (tentativa 1/3)...` e, no fim, `Backup DESISTIU de ...`
  → corrigir a causa e usar o botão `backup-notas-dev`.
