# Manter os dados sempre atualizados (automático, grátis, sem instalar nada)

Este pacote faz com que a oferta dos institutos politécnicos no site da FNAEESP se
atualize sozinha a partir da fonte oficial do IES — sem ninguém ter de correr programas.
Corre tudo na nuvem, no GitHub, que é gratuito.

Precisas de fazer isto **uma vez**. Depois é automático.

## O que este pacote contém
- `atualizar_dados_ies.py` — o programa que vai buscar os dados ao IES.
- `requirements.txt` — a lista de coisas que o programa precisa.
- `.github/workflows/atualizar-dados.yml` — a "receita" que diz ao GitHub para correr o programa todos os meses.

## Passo a passo

1. **Cria uma conta gratuita** em https://github.com (se ainda não tiveres).

2. **Cria um repositório novo**: carrega no `+` (canto superior direito) → *New repository*.
   - Nome: por exemplo `dados-politecnicos`.
   - Escolhe **Public** (público).
   - Carrega em *Create repository*.

3. **Carrega estes ficheiros** para o repositório:
   - Na página do repositório, carrega em *Add file* → *Upload files*.
   - Arrasta para lá **todos os ficheiros deste pacote**, incluindo a pasta `.github`.
     (Se o navegador não deixar arrastar a pasta `.github`, cria-a manualmente: *Add file*
     → *Create new file* → escreve `.github/workflows/atualizar-dados.yml` no nome e cola o
     conteúdo do ficheiro.)
   - Carrega em *Commit changes*.

4. **Liga as automatizações**: vai ao separador **Actions** (no topo do repositório).
   Se aparecer um aviso, carrega em *"I understand my workflows, go ahead and enable them"*.

5. **Faz a primeira recolha à mão** (para não esperares até ao dia 1):
   - Ainda em *Actions*, clica em **"Atualizar dados do IES"** (à esquerda) →
     botão **"Run workflow"** → **"Run workflow"**.
   - Espera alguns minutos. Quando terminar (fica com um visto verde ✓), o repositório
     passa a ter um ficheiro novo chamado **`dados_cursos.json`**.

6. **Copia o endereço (URL) do ficheiro** e cola-o no plugin:
   - No repositório, abre o ficheiro `dados_cursos.json` → carrega no botão **"Raw"**.
   - Copia o endereço que aparece na barra do navegador. É algo como:
     `https://raw.githubusercontent.com/OTEUNOME/dados-politecnicos/main/dados_cursos.json`
   - No WordPress: **Definições → Politécnicos FNAEESP** → cola esse endereço no campo do URL → **Guardar**.
   - Ainda aí, carrega em **"Atualizar agora"** para o site ir buscar os dados logo.

Pronto. A partir daqui:
- **Todos os meses** o GitHub vai buscar os dados novos ao IES sozinho.
- **Uma vez por semana** o WordPress vai buscar a versão mais recente ao GitHub sozinho.
- Não precisas de fazer mais nada.

## Notas
- As notas do último colocado de um ano só existem depois das colocações (setembro). O
  programa escolhe sempre automaticamente o ano mais recente que já tiver notas publicadas.
- Se quiseres forçar uma atualização a qualquer momento, repete o Passo 5 (*Run workflow*).
- A recolha demora alguns minutos porque percorre, com calma, todos os cursos de todos os
  institutos no portal do IES.
