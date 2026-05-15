"""
X Li — Onboarding v2
Foco: lojas dos últimos 15 dias — janela onde o CS ainda impacta.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date

st.set_page_config(page_title="Onboarding · X Li", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.block-container{padding:1.5rem 2rem 2rem!important;background:#FAFAF8;}
.main{background:#FAFAF8;}
[data-testid="stSidebarNav"]{display:none;}
.stButton>button{background:#0D4F4A!important;color:#D4F53C!important;
    font-weight:600!important;border:none!important;border-radius:8px!important;}
.stDownloadButton>button{background:#F2EDE4!important;color:#0D4F4A!important;
    font-weight:600!important;border:none!important;border-radius:8px!important;}
div[data-testid="stSelectbox"]>div>div{border-radius:8px!important;}
</style>
""", unsafe_allow_html=True)

# ── CONEXÃO ───────────────────────────────────────────────────────────────────
def rodar_sql(sql):
    import urllib.request, json as _j
    s   = st.secrets["metabase"]
    key = s.get("api_key", s.get("token",""))
    payload = _j.dumps({"database": int(s["db_id"]), "native": {"query": sql}, "type": "native"}).encode()
    req = urllib.request.Request(f"{s['url']}/api/dataset", data=payload,
        headers={"Content-Type":"application/json","x-api-key":key}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        d = _j.loads(r.read().decode())
    if "error" in d: raise Exception(d["error"])
    cols = [c["name"] for c in d["data"]["cols"]]
    return pd.DataFrame(d["data"]["rows"], columns=cols)

# ── HEADER ────────────────────────────────────────────────────────────────────
col_h, col_back = st.columns([6,1])
with col_h:
    st.markdown("""
    <div style='margin-bottom:1.5rem'>
        <div style='font-size:11px;color:#9DBDBB;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.3rem'>
            ⚡ X Li
        </div>
        <div style='font-size:24px;font-weight:800;color:#1A2E2B;line-height:1'>Onboarding</div>
        <div style='font-size:13px;color:#888;margin-top:.3rem'>
            Lojas dos últimos 15 dias · janela onde o CS ainda impacta
        </div>
    </div>
    """, unsafe_allow_html=True)
with col_back:
    st.page_link("app.py", label="← Início")

# ── QUERY ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def buscar_onboarding():
    return rodar_sql("""
    SELECT
        loja_id,
        COALESCE(upper(nome_loja), upper(dominio_loja), CAST(loja_id AS CHAR)) AS nome_loja,
        upper(segmento_loja)   AS segmento_loja,
        email_loja,
        data_cadastro_loja,
        data_primeira_venda,
        data_primeira_config_pagamento,
        data_primeira_config_logistica,
        data_primeira_config_produto,
        data_ini_plano_atual,
        upper(tipo_plano_atual) AS tipo_plano,
        vlr_plano_mrr_atual,
        'PAGO' AS status_plano,
        qtd_pedido_ultimos_30d,
        vlr_gmv_ultimos_30d,
        qtde_visitas_ultimos_30d,
        coalesce(datediff(current_date, data_cadastro_loja), 0) AS dias_cadastro,
        CASE
            WHEN data_primeira_config_produto   IS NULL THEN 'ONBOARDING INCOMPLETO'
            WHEN data_primeira_config_pagamento IS NULL THEN 'ONBOARDING INCOMPLETO'
            WHEN data_primeira_config_logistica IS NULL THEN 'ONBOARDING INCOMPLETO'
            WHEN data_primeira_venda            IS NULL THEN 'NUNCA VENDEU'
            ELSE 'LOJA ATIVA'
        END AS status_loja
    FROM analytics_manual.mv_loja
    WHERE situacao_loja = 'ativa'
      AND data_cadastro_loja >= current_date - interval '15' day
      AND data_ini_plano_atual IS NOT NULL
    ORDER BY data_cadastro_loja DESC
    """)

try:
    with st.spinner("Carregando fila de onboarding..."):
        df = buscar_onboarding()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

if df.empty:
    st.success("✅ Nenhuma loja em onboarding nos últimos 15 dias.")
    st.stop()

# ── SCORE + GARGALO ───────────────────────────────────────────────────────────
df["dias_cadastro"] = pd.to_numeric(df["dias_cadastro"], errors="coerce").fillna(0).astype(int)

def _gargalo(row):
    if str(row.get("data_primeira_config_produto","")) in ("","None","nan","NaT"):
        return "Sem produto"
    if str(row.get("data_primeira_config_pagamento","")) in ("","None","nan","NaT"):
        return "Sem pagamento"
    if str(row.get("data_primeira_config_logistica","")) in ("","None","nan","NaT"):
        return "Sem frete"
    if str(row.get("data_primeira_venda","")) in ("","None","nan","NaT"):
        return "Nunca vendeu"
    return "Ativa"

def _acao(row):
    g = row.get("gargalo","")
    canal = "📞 Ligar" if row.get("dias_cadastro",0) >= 7 else "📧 E-mail"
    if g == "Sem produto":    return f"{canal} — cadastrar produto"
    if g == "Sem pagamento":  return f"{canal} — ativar Pagali"
    if g == "Sem frete":      return f"{canal} — configurar Enviali"
    if g == "Nunca vendeu":   return "📧 E-mail — guia de primeiras vendas"
    return "👁️ Monitorar"

def _janela(row):
    d = int(row.get("dias_cadastro") or 0)
    if d >= 12: return "🔴 Crítica"
    if d >= 7:  return "🟡 Atenção"
    return "🟢 Aberta"

def _score(row):
    base = 0
    if row.get("gargalo") == "Sem produto":   base = 60
    elif row.get("gargalo") == "Sem pagamento": base = 70
    elif row.get("gargalo") == "Sem frete":   base = 50
    elif row.get("gargalo") == "Nunca vendeu": base = 40
    d = int(row.get("dias_cadastro") or 0)
    if d >= 12: base = min(base + 15, 100)
    elif d >= 7: base = min(base + 7, 100)
    return base

df["gargalo"] = df.apply(_gargalo, axis=1)
df["acao_cs"] = df.apply(_acao, axis=1)
df["janela"]  = df.apply(_janela, axis=1)
df["score"]   = df.apply(_score, axis=1)
df = df.sort_values(["score","dias_cadastro"], ascending=[False,False]).reset_index(drop=True)

# ── MÉTRICAS ──────────────────────────────────────────────────────────────────
n_total    = len(df)
n_critico  = len(df[df["janela"] == "🔴 Crítica"])
n_atencao  = len(df[df["janela"] == "🟡 Atenção"])
n_aberta   = len(df[df["janela"] == "🟢 Aberta"])
n_sem_pag  = len(df[df["gargalo"] == "Sem pagamento"])
n_sem_prod = len(df[df["gargalo"] == "Sem produto"])
mrr_risco  = pd.to_numeric(df["vlr_plano_mrr_atual"], errors="coerce").fillna(0).sum()

def fmt_brl(v):
    return f"R${float(v):,.0f}".replace(",","X").replace(".",",").replace("X",".")

# Cards de métricas
c1,c2,c3,c4,c5 = st.columns(5)
for col, label, valor, cor in [
    (c1, "Total (15 dias)",      str(n_total),       "#1A2E2B"),
    (c2, "🔴 Janela crítica",    str(n_critico),     "#E24B4A"),
    (c3, "🟡 Atenção",           str(n_atencao),     "#F59E0B"),
    (c4, "💳 Sem pagamento",     str(n_sem_pag),     "#6366F1"),
    (c5, "💰 MRR em risco",      fmt_brl(mrr_risco), "#0D4F4A"),
]:
    with col:
        st.markdown(
            f"<div style='background:white;border:1.5px solid #E8E4DE;border-radius:12px;"
            f"padding:.8rem 1rem'>"
            f"<div style='font-size:11px;color:#888;margin-bottom:.3rem'>{label}</div>"
            f"<div style='font-size:24px;font-weight:800;color:{cor}'>{valor}</div>"
            f"</div>", unsafe_allow_html=True)

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# ── COHORT POR FAIXA ──────────────────────────────────────────────────────────
st.markdown("#### Onde estão as lojas")

df["faixa"] = pd.cut(df["dias_cadastro"],
    bins=[-1, 3, 7, 11, 15],
    labels=["0–3 dias", "4–7 dias", "8–11 dias", "12–15 dias"])

cohort = df.groupby("faixa", observed=True).agg(
    total=("loja_id","count"),
    criticos=("janela", lambda x: (x=="🔴 Crítica").sum()),
    sem_pagamento=("gargalo", lambda x: (x=="Sem pagamento").sum()),
    venderam=("data_primeira_venda", lambda x: x.notna().sum()),
    mrr=("vlr_plano_mrr_atual", lambda x: pd.to_numeric(x,errors="coerce").fillna(0).sum()),
).reset_index()

cols_c = st.columns(4)
urgencia = {"0–3 dias": ("🟢","#166534","#F0FDF4"), "4–7 dias": ("🟡","#92400E","#FFFBEB"),
            "8–11 dias": ("🟠","#92400E","#FEF3C7"), "12–15 dias": ("🔴","#991B1B","#FEF2F2")}

for col, (_, row) in zip(cols_c, cohort.iterrows()):
    with col:
        emoji, cor_t, bg = urgencia.get(str(row["faixa"]), ("⚪","#888","#F5F2EE"))
        taxa = round(row["venderam"]/row["total"]*100,1) if row["total"] > 0 else 0
        st.markdown(
            f"<div style='background:{bg};border-radius:12px;padding:1rem;margin-bottom:.5rem'>"
            f"<div style='font-size:11px;font-weight:700;color:{cor_t};text-transform:uppercase;"
            f"letter-spacing:.08em;margin-bottom:.5rem'>{emoji} {row['faixa']}</div>"
            f"<div style='font-size:28px;font-weight:800;color:#1A2E2B;line-height:1'>{int(row['total'])}</div>"
            f"<div style='font-size:11px;color:#888;margin-bottom:.8rem'>lojas pagas</div>"
            f"<div style='display:flex;justify-content:space-between;font-size:12px'>"
            f"<div><span style='color:#888'>Sem pgto</span><br>"
            f"<strong style='color:{cor_t}'>{int(row['sem_pagamento'])}</strong></div>"
            f"<div><span style='color:#888'>Já vendeu</span><br>"
            f"<strong style='color:#166534'>{int(row['venderam'])}</strong></div>"
            f"<div><span style='color:#888'>Conv.</span><br>"
            f"<strong style='color:#1A2E2B'>{taxa:.0f}%</strong></div>"
            f"</div></div>",
            unsafe_allow_html=True)

st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

# ── FILTROS ───────────────────────────────────────────────────────────────────
cf1,cf2,cf3 = st.columns(3)
with cf1: f_gargalo = st.selectbox("Gargalo", ["Todos","Sem produto","Sem pagamento","Sem frete","Nunca vendeu"])
with cf2: f_janela  = st.selectbox("Urgência", ["Todos","🔴 Crítica","🟡 Atenção","🟢 Aberta"])
with cf3: f_seg     = st.selectbox("Segmento", ["Todos"] + sorted(df["segmento_loja"].dropna().unique().tolist()))

dv = df.copy()
if f_gargalo != "Todos": dv = dv[dv["gargalo"] == f_gargalo]
if f_janela  != "Todos": dv = dv[dv["janela"]  == f_janela]
if f_seg     != "Todos": dv = dv[dv["segmento_loja"] == f_seg]

st.caption(f"{len(dv)} loja(s) · ordenadas por urgência")

# ── TABELA ────────────────────────────────────────────────────────────────────
cols_show = [c for c in ["loja_id","nome_loja","segmento_loja","dias_cadastro",
                          "gargalo","janela","acao_cs","email_loja"] if c in dv.columns]
st.dataframe(
    dv[cols_show].rename(columns={
        "loja_id":"ID","nome_loja":"Loja","segmento_loja":"Segmento",
        "dias_cadastro":"Dias","gargalo":"Gargalo",
        "janela":"Urgência","acao_cs":"Ação CS","email_loja":"E-mail",
    }),
    use_container_width=True, hide_index=True,
)

st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
st.download_button("⬇️ Exportar CSV",
    data=dv[cols_show].to_csv(index=False).encode("utf-8"),
    file_name=f"onboarding_{date.today().strftime('%Y%m%d')}.csv",
    mime="text/csv")
