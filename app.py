import streamlit as st
import os

st.set_page_config(page_title="X Li", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.block-container{padding:3rem 3rem 2rem!important;background:#FAFAF8;}
.main{background:#FAFAF8;}
[data-testid="stSidebarNav"]{display:none;}
[data-testid="stAppViewContainer"]{background:#FAFAF8;}
footer{display:none;}
.stButton>button{
    background:#0D4F4A!important;color:#D4F53C!important;
    font-weight:600!important;font-size:13px!important;
    border-radius:8px!important;border:none!important;
    padding:.6rem 1.2rem!important;
}
</style>
""", unsafe_allow_html=True)

base      = os.path.dirname(os.path.abspath(__file__))
onb_path  = os.path.join(base, "pages", "1_Onboarding.py")
raio_path = os.path.join(base, "pages", "2_raio_x.py")

# ── Carrega número de onboarding ──────────────────────────────────────────────
n_onb = None
try:
    import urllib.request, json as _j
    s   = st.secrets["metabase"]
    key = s.get("api_key", s.get("token",""))
    payload = _j.dumps({"database": int(s["db_id"]), "type": "native", "native": {"query": """
        SELECT COUNT(*) FROM analytics_manual.mv_loja
        WHERE situacao_loja = 'ativa'
          AND data_cadastro_loja >= current_date - interval '60' day
          AND upper(tipo_plano_atual) != 'GRATIS'
          AND vlr_plano_mrr_atual > 0
          AND (data_primeira_config_pagamento IS NULL
            OR data_primeira_config_logistica IS NULL
            OR data_primeira_config_produto   IS NULL
            OR data_primeira_venda IS NULL)
    """}}).encode()
    req = urllib.request.Request(f"{s['url']}/api/dataset", data=payload,
        headers={"Content-Type":"application/json","x-api-key":key}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        d = _j.loads(r.read().decode())
    n_onb = int(d["data"]["rows"][0][0])
except Exception:
    pass

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='margin-bottom:3rem'>
    <div style='display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem'>
        <span style='font-size:18px'>⚡</span>
        <span style='font-size:22px;font-weight:800;color:#0D4F4A;letter-spacing:-0.5px'>X Li</span>
    </div>
    <div style='font-size:13px;color:#9DBDBB'>Inteligência de lojistas · Loja Integrada</div>
</div>
""", unsafe_allow_html=True)

# ── CARDS ─────────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2, gap="large")

with col1:
    n_str = f"<div style='font-size:56px;font-weight:800;color:#0D4F4A;line-height:1;margin-bottom:.2rem'>{n_onb:,}</div><div style='font-size:12px;color:#9DBDBB;margin-bottom:1.5rem'>lojas com onboarding incompleto hoje</div>" if n_onb is not None else "<div style='height:1.5rem'></div>"
    st.markdown(f"""
    <div style='border:1.5px solid #E8E4DE;border-radius:16px;padding:2rem;background:white;min-height:260px'>
        <div style='font-size:11px;font-weight:700;color:#9DBDBB;text-transform:uppercase;
                    letter-spacing:.1em;margin-bottom:1.5rem'>Onboarding</div>
        {n_str}
        <div style='font-size:18px;font-weight:700;color:#1A2E2B;margin-bottom:.5rem;line-height:1.3'>
            Fila de lojas novas
        </div>
        <div style='font-size:13px;color:#888;line-height:1.7'>
            Gargalo identificado e ação recomendada.<br>
            CS vê o que fazer sem precisar diagnosticar.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    if st.button("Abrir Onboarding →", use_container_width=True, key="btn_onb"):
        st.switch_page(onb_path)

with col2:
    st.markdown(f"""
    <div style='border:1.5px solid #0D4F4A;border-radius:16px;padding:2rem;background:#0D4F4A;min-height:260px'>
        <div style='font-size:11px;font-weight:700;color:#1ABCB0;text-transform:uppercase;
                    letter-spacing:.1em;margin-bottom:1.5rem'>Raio X</div>
        <div style='font-size:56px;font-weight:800;color:#D4F53C;line-height:1;margin-bottom:.2rem'>Top 100</div>
        <div style='font-size:12px;color:#9DBDBB;margin-bottom:1.5rem'>melhores lojistas monitorados</div>
        <div style='font-size:18px;font-weight:700;color:white;margin-bottom:.5rem;line-height:1.3'>
            Top sellers em risco
        </div>
        <div style='font-size:13px;color:#9DBDBB;line-height:1.7'>
            O app identifica automaticamente quem está<br>
            em queda e abre o diagnóstico completo.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    if st.button("Abrir Raio X →", use_container_width=True, key="btn_raio"):
        st.switch_page(raio_path)

# ── RODAPÉ ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='margin-top:3rem;padding-top:1.5rem;border-top:1px solid #E8E4DE;
            display:flex;justify-content:space-between;align-items:center'>
    <div style='font-size:11px;color:#C8C0B4'>
        Loja Integrada · Time de Automação N2 · 2026
    </div>
    <div style='font-size:11px;color:#C8C0B4'>raioxli.streamlit.app</div>
</div>
""", unsafe_allow_html=True)
