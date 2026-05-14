"""
X Li — Onboarding
Fila de lojas novas com gargalo e ação inline.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date

st.set_page_config(page_title="Onboarding · X Li", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.block-container{padding:1.2rem 2rem 2rem;background:#F2EDE4;}
.main{background:#F2EDE4;}
[data-testid="stSidebarNav"]{display:none;}
.stButton>button{background:#0D4F4A!important;color:#D4F53C!important;
    font-weight:600!important;border:none!important;border-radius:10px!important;}
.stDownloadButton>button{background:#1ABCB0!important;color:#0D4F4A!important;
    font-weight:600!important;border:none!important;border-radius:10px!important;}
</style>
""", unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='background:#0D4F4A;border-radius:14px;padding:1rem 1.5rem;
            margin-bottom:1.2rem;display:flex;align-items:center;justify-content:space-between'>
    <div>
        <div style='font-size:20px;font-weight:700;color:#D4F53C'>🚀 Onboarding</div>
        <div style='font-size:12px;color:#9DBDBB;margin-top:2px'>
            Lojas novas · gargalo identificado · ação inline
        </div>
    </div>
    <a href='/' target='_self' style='font-size:12px;color:#9DBDBB;text-decoration:none'>
        ← X Li
    </a>
</div>
""", unsafe_allow_html=True)

# ── CONEXÃO ───────────────────────────────────────────────────────────────────
def _ok():
    try:
        cfg = st.secrets["metabase"]
        return bool(cfg.get("url") and ("api_key" in cfg or "token" in cfg))
    except Exception:
        return False

def rodar_sql(sql):
    import urllib.request, json as _json, time
    s   = st.secrets["metabase"]
    key = s.get("api_key", s.get("token", ""))
    payload = _json.dumps({"database": int(s["db_id"]), "native": {"query": sql}, "type": "native"}).encode()
    req = urllib.request.Request(
        f"{s['url']}/api/dataset", data=payload,
        headers={"Content-Type": "application/json", "x-api-key": key}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = _json.loads(resp.read().decode())
    if "error" in data:
        raise Exception(data["error"])
    cols = [c["name"] for c in data["data"]["cols"]]
    return pd.DataFrame(data["data"]["rows"], columns=cols)

@st.cache_data(ttl=600)
def buscar_onboarding():
    return rodar_sql("""
    SELECT
        loja_id,
        COALESCE(upper(nome_loja), upper(dominio_loja), CAST(loja_id AS CHAR)) AS nome_loja,
        upper(segmento_loja)   AS segmento_loja,
        upper(situacao_loja)   AS situacao_loja,
        data_cadastro_loja,
        data_primeira_venda,
        qtd_pedido_ultimos_30d,
        vlr_gmv_ultimos_30d,
        qtde_visitas_ultimos_30d,
        data_primeira_config_pagamento,
        data_primeira_config_logistica,
        data_primeira_config_produto,
        data_ini_plano_atual,
        CASE WHEN data_ini_plano_atual IS NOT NULL THEN 'PAGO' ELSE 'GRÁTIS' END AS status_plano,
        CASE
            WHEN data_primeira_config_pagamento IS NULL
              OR data_primeira_config_logistica IS NULL
              OR data_primeira_config_produto   IS NULL THEN 'ONBOARDING INCOMPLETO'
            WHEN data_primeira_venda IS NULL            THEN 'NUNCA VENDEU'
            WHEN coalesce(vlr_gmv_ultimos_30d,0) = 0   THEN 'SEM VENDAS RECENTES'
            ELSE 'LOJA ATIVA'
        END AS status_loja,
        coalesce(datediff(current_date, data_cadastro_loja), 0) AS dias_cadastro
    FROM analytics_manual.mv_loja
    WHERE situacao_loja = 'ativa'
      AND data_cadastro_loja >= current_date - interval '60' day
      AND (
            data_primeira_config_pagamento IS NULL
         OR data_primeira_config_logistica IS NULL
         OR data_primeira_config_produto   IS NULL
         OR data_primeira_venda            IS NULL
         OR coalesce(vlr_gmv_ultimos_30d,0) = 0
      )
    ORDER BY
        CASE WHEN data_ini_plano_atual IS NOT NULL THEN 0 ELSE 1 END ASC,
        dias_cadastro DESC
    """)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def _gargalo(row):
    if str(row.get("data_primeira_config_produto","")) in ("","None","nan","NaT"):
        return "🔴 Sem produto"
    if str(row.get("data_primeira_config_pagamento","")) in ("","None","nan","NaT"):
        return "🔴 Sem pagamento"
    if str(row.get("data_primeira_config_logistica","")) in ("","None","nan","NaT"):
        return "🟡 Sem frete"
    if str(row.get("data_primeira_venda","")) in ("","None","nan","NaT"):
        return "🟠 Nunca vendeu"
    return "✅ OK"

def _acao(row):
    g = row.get("gargalo","")
    if "produto"   in g: return "📦 Ligar — cadastrar produto"
    if "pagamento" in g: return "💳 Ligar — ativar Pagali"
    if "frete"     in g: return "📬 E-mail — configurar Enviali"
    if "vendeu"    in g: return "📢 E-mail — guia de divulgação"
    return "👁️ Monitorar"

def _janela(row):
    d = int(row.get("dias_cadastro") or 0)
    if d >= 15: return "⚠️ Vencida"
    if d >= 7:  return "🕐 Crítica"
    return "🟢 Aberta"

# ── MAIN ──────────────────────────────────────────────────────────────────────
if not _ok():
    st.error("Metabase não conectado. Verifique as credenciais em .streamlit/secrets.toml")
    st.stop()

with st.spinner("Carregando fila de onboarding..."):
    try:
        df = buscar_onboarding()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()

if df.empty:
    st.success("✅ Nenhuma loja em onboarding incompleto agora.")
    st.stop()

# Score
df["dias_cadastro"] = pd.to_numeric(df["dias_cadastro"], errors="coerce").fillna(0).astype(int)
_s = df["status_loja"].fillna("")
_d = df["dias_cadastro"]
_p = df["status_plano"].fillna("").str.upper()
_sc = np.where(_s=="ONBOARDING INCOMPLETO", np.where(_d>=7,70,50),
       np.where(_s=="NUNCA VENDEU",          np.where(_d>=20,45,25),
       np.where(_s=="SEM VENDAS RECENTES",   55, 5)))
df["score"]   = np.where(_p=="PAGO", np.minimum(_sc+10,100), _sc).astype(int)
df["gargalo"] = df.apply(_gargalo, axis=1)
df["acao_cs"] = df.apply(_acao, axis=1)
df["janela"]  = df.apply(_janela, axis=1)
df["mes_entrada"] = pd.to_datetime(df["data_cadastro_loja"], errors="coerce").dt.strftime("%Y-%m").fillna("—")
df = df.sort_values("score", ascending=False)

# Métricas
n_total   = len(df[df["status_loja"] != "LOJA ATIVA"])
n_critico = len(df[df["score"] >= 70])
n_pago    = len(df[(df["status_plano"].str.upper()=="PAGO") & (df["status_loja"]!="LOJA ATIVA")])
n_janela  = len(df[(df["dias_cadastro"]>=7) & (df["status_loja"]!="LOJA ATIVA")])

c1,c2,c3,c4 = st.columns(4)
c1.metric("Lojas em onboarding", n_total)
c2.metric("🔴 Score crítico (70+)", n_critico)
c3.metric("💸 Pagos travados", n_pago)
c4.metric("⏰ Passaram janela", n_janela)
st.divider()

# Filtros
_nomes_mes = {"01":"Jan","02":"Fev","03":"Mar","04":"Abr","05":"Mai","06":"Jun",
              "07":"Jul","08":"Ago","09":"Set","10":"Out","11":"Nov","12":"Dez"}
def _fmt(m):
    try: a,n = m.split("-"); return f"{_nomes_mes.get(n,n)}/{a}"
    except: return m

meses = sorted([m for m in df["mes_entrada"].unique() if m != "—"], reverse=True)
meses_labels = {m: _fmt(m) for m in meses}
_lv = {v:k for k,v in meses_labels.items()}

cf1,cf2,cf3,cf4 = st.columns(4)
with cf1: f_mes     = st.selectbox("Mês", ["Todos"]+[meses_labels[m] for m in meses])
with cf2: f_gargalo = st.selectbox("Gargalo", ["Todos","🔴 Sem produto","🔴 Sem pagamento","🟡 Sem frete","🟠 Nunca vendeu"])
with cf3: f_plano   = st.selectbox("Plano", ["Todos","PAGO","GRÁTIS"])
with cf4: f_janela  = st.selectbox("Janela", ["Todos","🟢 Aberta","🕐 Crítica","⚠️ Vencida"])

dv = df[df["status_loja"] != "LOJA ATIVA"].copy()
if f_mes     != "Todos": dv = dv[dv["mes_entrada"] == _lv.get(f_mes, f_mes)]
if f_gargalo != "Todos": dv = dv[dv["gargalo"] == f_gargalo]
if f_plano   != "Todos": dv = dv[dv["status_plano"].str.upper().str.replace("GRÁTIS","GRÁTIS") == f_plano]
if f_janela  != "Todos": dv = dv[dv["janela"] == f_janela]

st.caption(f"{len(dv)} loja(s) encontrada(s)")

cols_show = [c for c in ["loja_id","nome_loja","segmento_loja","status_plano",
                          "score","dias_cadastro","gargalo","janela","acao_cs"] if c in dv.columns]
st.dataframe(
    dv[cols_show].rename(columns={
        "loja_id":"ID","nome_loja":"Loja","segmento_loja":"Segmento",
        "status_plano":"Plano","score":"Score","dias_cadastro":"Dias",
        "gargalo":"Gargalo","janela":"Janela","acao_cs":"Ação CS",
    }),
    use_container_width=True, hide_index=True,
    column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")},
)

st.download_button("⬇️ Exportar CSV",
    data=dv[cols_show].to_csv(index=False).encode("utf-8"),
    file_name=f"onboarding_{date.today().strftime('%Y%m%d')}.csv",
    mime="text/csv")

st.divider()

# ── COHORT ────────────────────────────────────────────────────────────────────
st.markdown("#### 📊 Cohort — % que já vendeu por mês de entrada")
cohort = df[df["status_loja"]!="LOJA ATIVA"].groupby("mes_entrada").agg(
    total=("loja_id","count"),
    venderam=("data_primeira_venda", lambda x: x.notna().sum()),
    pagos=("status_plano", lambda x: (x.str.upper()=="PAGO").sum()),
    criticos=("score", lambda x: (pd.to_numeric(x,errors="coerce")>=70).sum()),
).reset_index().sort_values("mes_entrada", ascending=False)

cohort["% vendeu"]   = (cohort["venderam"] / cohort["total"] * 100).round(1)
cohort["% pagos"]    = (cohort["pagos"]    / cohort["total"] * 100).round(1)
cohort["% críticos"] = (cohort["criticos"] / cohort["total"] * 100).round(1)
cohort["Mês"]        = cohort["mes_entrada"].apply(_fmt)

cols_c = st.columns(min(len(cohort), 4))
for i, (_, rc) in enumerate(cohort.iterrows()):
    with cols_c[i % 4]:
        pv  = float(rc["% vendeu"])
        cor = "#1ABCB0" if pv >= 30 else "#F59E0B" if pv >= 10 else "#E24B4A"
        st.markdown(
            f"<div style='background:white;border-radius:10px;padding:.8rem;margin-bottom:8px'>"
            f"<div style='font-size:13px;font-weight:700;color:#1A2E2B'>{rc['Mês']}</div>"
            f"<div style='font-size:11px;color:#888;margin:.2rem 0'>{int(rc['total'])} lojas</div>"
            f"<div style='display:flex;gap:6px;margin-top:.4rem'>"
            f"<div style='flex:1;background:#F0FDF4;border-radius:6px;padding:.3rem;text-align:center'>"
            f"<div style='font-size:16px;font-weight:800;color:{cor}'>{pv:.0f}%</div>"
            f"<div style='font-size:10px;color:#888'>vendeu</div></div>"
            f"<div style='flex:1;background:#FEF2F2;border-radius:6px;padding:.3rem;text-align:center'>"
            f"<div style='font-size:16px;font-weight:800;color:#E24B4A'>{rc['% críticos']:.0f}%</div>"
            f"<div style='font-size:10px;color:#888'>críticos</div></div>"
            f"<div style='flex:1;background:#EEEDFE;border-radius:6px;padding:.3rem;text-align:center'>"
            f"<div style='font-size:16px;font-weight:800;color:#6366F1'>{rc['% pagos']:.0f}%</div>"
            f"<div style='font-size:10px;color:#888'>pagos</div></div>"
            f"</div></div>", unsafe_allow_html=True)
