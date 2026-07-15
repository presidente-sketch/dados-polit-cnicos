#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
atualizar_dados_ies.py
======================
Recolhe a oferta formativa OFICIAL do ensino superior público politécnico a
partir do portal do Instituto para o Ensino Superior (IES, I.P. — ex-DGES) e
gera o ficheiro `dados_cursos.json` que alimenta a aplicação
"Encontra o teu Politécnico" da FNAEESP.

Fonte oficial (verificada):
  • Índice instituição/curso (politécnico público):
      https://www.dges.gov.pt/guias/indest.asp?reg=12
  • Detalhe de cada par instituição/curso:
      https://www.dges.gov.pt/guias/detcursopi.asp?codc={codc}&code={code}
    -> contém grau, área CNAEF, ECTS, vagas, provas de ingresso,
       classificações mínimas e a NOTA DO ÚLTIMO COLOCADO (2023/2024/2025).

IMPORTANTE
  - Este script tem de correr num ambiente com acesso à internet ao
    domínio dges.gov.pt (o portal do IES). Não corre dentro de sandboxes
    com lista de domínios restrita.
  - É deliberadamente "educado": faz pausa entre pedidos e usa cache local,
    para não sobrecarregar o servidor do IES. A oferta nacional tem centenas
    de pares instituição/curso — a primeira recolha demora alguns minutos.
  - As notas do último colocado de 2026 só existem depois de fechar o
    concurso (agosto/setembro de 2026). Até lá usa-se o valor de 2025.

Uso:
    pip install requests beautifulsoup4
    python atualizar_dados_ies.py                 # oferta pública politécnica
    python atualizar_dados_ies.py --reg 22         # politécnico privado
    python atualizar_dados_ies.py --ano 2024       # nota do último colocado de 2024
    python atualizar_dados_ies.py --sem-cache      # ignora a cache local

Saída:
    dados_cursos.json   (mesmo esquema que a app consome)
"""

import argparse, json, os, re, sys, time, unicodedata, datetime
import requests
from bs4 import BeautifulSoup

BASE = "https://www.dges.gov.pt/guias"
HEADERS = {"User-Agent": "FNAEESP-OfertaPolitecnica/1.0 (+geral@fnaeesp.pt)"}
CACHE_DIR = ".cache_ies"
PAUSA = 0.6  # segundos entre pedidos (ser simpático com o servidor)

# ----------------------------------------------------------------------------
# Mapa de cada par instituição/curso para uma das 6 áreas da app.
# Regra por palavra-chave (mais fiável para o utilizador) + recurso ao CNAEF.
# ----------------------------------------------------------------------------
AREA_RULES = [
 ("saude", ["enfermagem","fisioterapia","farmac","biomedic","radiolog","imagem medica",
            "diet","nutri","terapia","cardiopneumo","saude","analises clinic","higiene oral",
            "osteopat","optometr","ortoptica","protesia","fisiologia"]),
 ("tec",   ["engenharia","informatic","program","redes","ciberseguranca","tecnolog","eletro",
            "mecanic","civil","energias","robotic","computad","sistemas de informacao",
            "biotecnolog","agronom","ambiente","alimentar","zootecnic","enologia","maquinas",
            "quimica","topografia","biomedica","aeronautic","naval","maritima"]),
 ("art",   ["design","artes","musica","fotograf","som e imagem","audiovisual","multimedia",
            "ceramica","teatro","danca","ilustra","jogos digitais","conservacao e restauro",
            "cinema","video"]),
 ("com",   ["comunicacao","jornalismo","publicidade","relacoes publicas","media","editorial"]),
 ("edu",   ["educacao","servico social","animacao","desporto","gerontolog","intervencao social",
            "professor","ensino basico","reabilitacao psicomotora"]),
 ("gest",  ["gestao","contabilid","administracao","comercio","solicitad","logistica","turismo",
            "hotel","financas","economia","recursos humanos","banc","seguros","marketing",
            "portuaria","lazer","fiscal","imobiliar"]),
]
CNAEF_FALLBACK = {"72":"saude","76":"edu","48":"tec","52":"tec","54":"tec","58":"tec",
                  "84":"tec","34":"gest","81":"gest","14":"edu","38":"edu","21":"art",
                  "32":"com","22":"com","62":"tec","85":"tec"}

# Estabelecimento (escola) -> (instituto curto, cidade, distrito).
# Preencher/ajustar conforme necessário; se faltar, a cidade é lida da página
# de detalhe (endereço da instituição) e o distrito fica = cidade.
PARENT_HINTS = {
 "politecnico de lisboa": ("Politécnico de Lisboa","Lisboa","Lisboa"),
 "politecnico do porto":  ("Politécnico do Porto","Porto","Porto"),
 "politecnico de coimbra":("Politécnico de Coimbra","Coimbra","Coimbra"),
 "politecnico de leiria": ("Politécnico de Leiria","Leiria","Leiria"),
 "politecnico de setubal":("Politécnico de Setúbal","Setúbal","Setúbal"),
 "politecnico de santarem":("Politécnico de Santarém","Santarém","Santarém"),
 "politecnico de braganca":("Politécnico de Bragança","Bragança","Bragança"),
 "politecnico de viana do castelo":("Politécnico de Viana do Castelo","Viana do Castelo","Viana do Castelo"),
 "politecnico do cavado e do ave":("Politécnico do Cávado e do Ave","Barcelos","Braga"),
 "politecnico de viseu":  ("Politécnico de Viseu","Viseu","Viseu"),
 "politecnico da guarda": ("Politécnico da Guarda","Guarda","Guarda"),
 "politecnico de castelo branco":("Politécnico de Castelo Branco","Castelo Branco","Castelo Branco"),
 "politecnico de portalegre":("Politécnico de Portalegre","Portalegre","Portalegre"),
 "politecnico de beja":   ("Politécnico de Beja","Beja","Beja"),
 "politecnico de tomar":  ("Politécnico de Tomar","Tomar","Santarém"),
 "hotelaria e turismo do estoril":("Esc. Sup. de Hotelaria e Turismo do Estoril","Estoril","Lisboa"),
 "nautica infante d. henrique":("Esc. Sup. Náutica Infante D. Henrique","Paço de Arcos","Lisboa"),
}
# código postal -> distrito (amostra; alargar à vontade)
CP_DISTRITO = {
 "1":"Lisboa","2":"Setúbal","3":"Leiria","4":"Porto","5":"Vila Real","6":"Castelo Branco",
 "7":"Évora","8":"Faro","9":"Madeira",
}

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn').lower()

def map_area(name, cnaef=""):
    n = strip_accents(name)
    for area, kws in AREA_RULES:
        if any(k in n for k in kws):
            return area
    return CNAEF_FALLBACK.get((cnaef or "")[:2], "gest")

def parent_for(escola):
    e = strip_accents(escola)
    for key, val in PARENT_HINTS.items():
        if key in e:
            return val
    # fallback: usa o nome antes do " - " como instituto
    short = escola.split(" - ")[0].strip()
    return (short, None, None)

# ----------------------------------------------------------------------------
# HTTP com cache local
# ----------------------------------------------------------------------------
def fetch(url, use_cache=True):
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = re.sub(r'[^a-zA-Z0-9]+', '_', url)[-120:] + ".html"
    path = os.path.join(CACHE_DIR, key)
    if use_cache and os.path.exists(path):
        return open(path, encoding="utf-8").read()
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.encoding = "windows-1252"          # as páginas .asp do IES são windows-1252
    html = r.text
    open(path, "w", encoding="utf-8").write(html)
    time.sleep(PAUSA)
    return html

# ----------------------------------------------------------------------------
# 1) Índice instituição/curso -> lista de pares (estab, codc, nome, grau, vagas)
# ----------------------------------------------------------------------------
def parse_index(reg):
    html = fetch(f"{BASE}/indest.asp?reg={reg}")
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    pares = []
    estab_code = estab_name = None
    # nas páginas, cada curso é um link detcursopi.asp?codc=..&code=..
    for a in soup.find_all("a", href=re.compile(r"detcursopi\.asp")):
        href = a["href"]
        m = re.search(r"codc=([A-Za-z0-9]+)&code=([A-Za-z0-9]+)", href)
        if not m:
            continue
        codc, code = m.group(1), m.group(2)
        nome = a.get_text(strip=True)
        pares.append({"code": code, "codc": codc, "name": nome,
                      "url": f"{BASE}/detcursopi.asp?codc={codc}&code={code}"})
    # remove duplicados
    seen, uniq = set(), []
    for p in pares:
        k = (p["code"], p["codc"])
        if k not in seen:
            seen.add(k); uniq.append(p)
    return uniq

# ----------------------------------------------------------------------------
# 2) Página de detalhe -> registo completo
# ----------------------------------------------------------------------------
def parse_detail(par, ano):
    html = fetch(par["url"])
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    g = lambda pat: (re.search(pat, text).group(1).strip() if re.search(pat, text) else None)

    escola = g(r"Detalhe de Curso\s*\n+\s*([^\n]+)\n") or ""
    if not escola:
        # a instituição costuma aparecer logo abaixo do nome do curso
        linhas = [l.strip() for l in text.split("\n") if l.strip()]
        escola = linhas[1] if len(linhas) > 1 else ""

    grau_raw = g(r"Grau:\s*([^\n]+)") or ""
    if "cnico Superior Profissional" in grau_raw or "TeSP" in grau_raw:
        degree = "TeSP"
    elif "Mestrado integrado" in grau_raw or "Mestrado Integrado" in grau_raw:
        degree = "Mestrado integrado"
    else:
        degree = "Licenciatura"

    cnaef = (g(r"CNAEF:\s*(\d+)") or "")
    dur = g(r"Dura[çc][ãa]o:\s*(\d+)\s*Semestres")
    years = round(int(dur)/2) if dur else None
    ects = int(g(r"ECTS:\s*(\d+)") or 0)
    vagas = int(g(r"Vagas para [\d/\-]+:\s*(\d+)") or 0)

    # provas de ingresso
    provas = []
    if "Provas de Ingresso" in text:
        bloco = text.split("Provas de Ingresso", 1)[1]
        bloco = re.split(r"Classifica|F[óo]rmula|Pr[ée]-?[Rr]equisitos", bloco)[0]
        provas = re.findall(r"\b\d{2}\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ ]+?)(?:\n|ou|$)", bloco)
        provas = sorted({p.strip() for p in provas if len(p.strip()) > 3})

    # nota do último colocado: linha "Último Colocado pelo Contingente Geral"
    grade = None
    row = re.search(r"[ÚU]ltimo Colocado[^\n|]*\|([^\n]+)", text)
    if row:
        nums = re.findall(r"\d+,\d+", row.group(1))
        # colunas por ordem cronológica, em pares (1ª fase, 2ª fase) por ano
        if str(ano) == "latest":
            # 1ª fase do ano mais recente: penúltimo valor se houver par completo, senão o último
            if len(nums) >= 2:
                grade = float(nums[-2 if len(nums) % 2 == 0 else -1].replace(",", "."))
            elif nums:
                grade = float(nums[-1].replace(",", "."))
        else:
            idx = {2023: 0, 2024: 2, 2025: 4}.get(int(ano), len(nums) - 2 if len(nums) >= 2 else 0)
            if 0 <= idx < len(nums):
                grade = float(nums[idx].replace(",", "."))

    short, city, region = parent_for(escola)
    if not city:
        cp = g(r"\n(\d{4})-\d{3}\s+([A-ZÀ-Ý ]+)")
        addr_city = (re.search(r"\d{4}-\d{3}\s+([A-Za-zÀ-ÿ ]+)", text) or [None, None])
        city = (addr_city[1].strip().title() if addr_city and addr_city[1] else None)
        region = CP_DISTRITO.get((cp or "")[:1], city) if cp else city

    return {
        "id": f"{par['code']}-{par['codc']}",
        "name": par["name"],
        "area": map_area(par["name"], cnaef),
        "degree": degree,
        "inst": short,
        "instName": escola,
        "city": city, "region": region,
        "ects": ects or 180,
        "years": years or 3,
        "grade": grade,
        "vagas": vagas,
        "exams": provas or ["Consultar provas no IES"],
        "url": par["url"],
    }

# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Recolhe a oferta politécnica oficial do IES.")
    ap.add_argument("--reg", default="12", help="12=politécnico público (default), 22=privado")
    ap.add_argument("--ano", default="latest", help="ano da nota do último colocado: 'latest' (default, escolhe o mais recente) ou 2023/2024/2025")
    ap.add_argument("--sem-cache", action="store_true", help="ignora a cache local")
    ap.add_argument("--saida", default="dados_cursos.json")
    args = ap.parse_args()

    global PAUSA
    print(f"› A obter o índice (reg={args.reg}) do IES…")
    pares = parse_index(args.reg)
    print(f"  {len(pares)} pares instituição/curso encontrados.")

    cursos, erros = [], 0
    for i, par in enumerate(pares, 1):
        try:
            cursos.append(parse_detail(par, args.ano))
        except Exception as e:
            erros += 1
            print(f"  ! falhou {par['url']}: {e}", file=sys.stderr)
        if i % 25 == 0:
            print(f"  … {i}/{len(pares)}")

    out = {
        "_meta": {
            "fonte": "Instituto para o Ensino Superior (IES, I.P.) — Guia da Candidatura",
            "url_fonte": f"{BASE}/indest.asp?reg={args.reg}",
            "tipo": "Ensino Superior Público Politécnico" if args.reg == "12" else "Ensino Superior Politécnico",
            "ano_nota_ultimo_colocado": ("mais recente disponível" if str(args.ano) == "latest" else args.ano),
            "gerado_em": datetime.date.today().isoformat(),
            "total": len(cursos),
        },
        "cursos": cursos,
    }
    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✓ {len(cursos)} cursos escritos em {args.saida} ({erros} erros).")

if __name__ == "__main__":
    main()
