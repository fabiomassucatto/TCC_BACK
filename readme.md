# Gestão de Transporte — TCC

Sistema web para confirmação de presença de estudantes/trabalhadores em
transporte coletivo, por meio de leitura de QR Code, com validação por
geolocalização (GPS) para evitar fraudes.

Protótipo em **Flask + SQLite**.

---

## Pré-requisitos

- **Python 3.10 ou superior** instalado na máquina
  Verifique com:
  ```bash
  python --version
  ```
  ou, em alguns sistemas (Linux/Mac):
  ```bash
  python3 --version
  ```

Não é necessário instalar SQLite separadamente — ele já vem incluso no
Python (módulo `sqlite3`).

---

## 1. Baixar/clonar o projeto

```bash
git clone <url-do-repositorio>
cd TCC_BACK
```

Se você recebeu o projeto como um `.zip`, apenas extraia e entre na pasta
pelo terminal.

---

## 2. Criar o ambiente virtual (venv)

O ambiente virtual isola as dependências do projeto do restante do seu
sistema. **Sempre crie um venv novo na sua máquina** — não reaproveite a
pasta `venv/` de outro computador, pois ela contém caminhos absolutos do
PC onde foi criada e não vai funcionar.

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

Quando o ambiente estiver ativado, o terminal mostra `(venv)` no início
da linha.

Para sair do ambiente virtual depois, basta digitar `deactivate`.

---

## 3. Instalar as dependências

Com o venv **ativado**, rode:

```bash
pip install -r requirements.txt
```

Isso instala:

| Pacote | Para que serve |
|---|---|
| `Flask` | Framework web (rotas, sessão, templates) |
| `qrcode` | Geração das imagens de QR Code |
| `Pillow` | Manipulação de imagens (dependência do `qrcode`) |

> `sqlite3` **não** está na lista porque já vem embutido no Python — não
> precisa instalar.

---

## 4. Rodar o projeto

Ainda com o venv ativado, na pasta do projeto:

```bash
python app.py
```

Se aparecer algo como:

```
* Running on http://127.0.0.1:5000
```

o servidor está no ar. Abra esse endereço no navegador.

O banco de dados (`database.db`) é criado automaticamente na primeira
execução, caso ainda não exista — não precisa rodar nenhum script de
migração à parte.

---

## 5. Acessando pelo celular (necessário para testar câmera/GPS)

Como o projeto usa câmera (leitura de QR Code) e geolocalização, é
necessário testar em um celular real, não só no navegador do PC.

1. Descubra o IP local do computador que está rodando o Flask:
   - Windows: `ipconfig` (procure por "Endereço IPv4")
   - Linux/Mac: `ifconfig` ou `ip a`
2. Rode o Flask aceitando conexões externas:
   ```bash
   flask --app app run --host=0.0.0.0
   ```
   ou edite a última linha do `app.py` para:
   ```python
   app.run(debug=True, host="0.0.0.0")
   ```
3. No celular (conectado à **mesma rede Wi-Fi**), acesse:
   ```
   http://<IP_DO_PC>:5000
   ```

> Navegadores modernos só liberam câmera e GPS em conexões HTTPS ou em
> `localhost`. Para testes na mesma rede via IP (HTTP puro), alguns
> navegadores podem bloquear esse acesso. Se isso ocorrer, uma alternativa
> é usar uma ferramenta de túnel como o [ngrok](https://ngrok.com/) para
> expor o `localhost:5000` por HTTPS temporariamente.

---

## Estrutura do projeto

```
TCC_BACK/
├── app.py                 # Backend Flask (rotas, lógica, banco)
├── database.db            # Banco SQLite (gerado automaticamente)
├── requirements.txt        # Dependências Python
├── static/
│   ├── img.png
│   └── styles.css
└── templates/
    ├── usuario.html         # Página inicial
    ├── login.html           # Login de usuário
    ├── cadastro.html         # Cadastro de usuário
    ├── motorista_login.html  # Login do motorista
    ├── exibir_qr.html        # Leitura do QR Code (câmera)
    └── dashboard.html        # Painel com totais por ponto
```

---

## Problemas comuns

**`ModuleNotFoundError: No module named 'flask'`**
O venv não está ativado, ou as dependências não foram instaladas dentro
dele. Repita os passos 2 e 3.

**`database.db` com dados antigos/zerados**
O banco é o mesmo arquivo entre execuções. Para resetar o banco do zero,
basta apagar o arquivo `database.db` e rodar `python app.py` novamente.

**Porta 5000 já em uso**
Rode em outra porta:
```bash
flask --app app run --port=5001
```
