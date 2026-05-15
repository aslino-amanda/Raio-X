import streamlit as st
import os

st.set_page_config(page_title="X Li", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.block-container{padding:0!important;background:#0D4F4A;}
.main{background:#0D4F4A;}
[data-testid="stSidebarNav"]{display:none;}
[data-testid="stAppViewContainer"]{background:#0D4F4A;}
footer{display:none;}
.stPageLink a {
    display:none!important;
}
.stButton>button {
    background:#D4F53C!important;color:#0D4F4A!important;
    font-weight:700!important;font-size:14px!important;
    border-radius:10px!important;border:none!important;
    padding:.7rem 1rem!important;width:100%!important;
}
.stButton>button:hover {
    background:#C4E030!important;
}
/* fake old rule kept */
.__old_stPageLink a {
    display:block!important;width:100%!important;
    background:#D4F53C!important;color:#0D4F4A!important;
    font-weight:700!important;font-size:14px!important;
    border-radius:10px!important;padding:.7rem 1rem!important;
    text-align:center!important;text-decoration:none!important;
    border:none!important;
}
.stPageLink-raio a {
    background:#1A6A64!important;color:#D4F53C!important;
}
</style>
""", unsafe_allow_html=True)

base      = os.path.dirname(os.path.abspath(__file__))
onb_path  = os.path.join(base, "pages", "1_Onboarding.py")
raio_path = os.path.join(base, "pages", "2_raio_x.py")

# ── Tenta carregar números reais ──────────────────────────────────────────────
n_onb = n_risco = n_critico = gmv_risco = None
try:
    import urllib.request, json as _json
    s   = st.secrets["metabase"]
    key = s.get("api_key", s.get("token",""))

    def _sql(q):
        payload = _json.dumps({"database": int(s["db_id"]), "native": {"query": q}, "type": "native"}).encode()
        req = urllib.request.Request(f"{s['url']}/api/dataset", data=payload,
            headers={"Content-Type":"application/json","x-api-key":key}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            d = _json.loads(r.read().decode())
        return d["data"]["rows"]

    rows_onb = _sql("""
        SELECT COUNT(*) FROM analytics_manual.mv_loja
        WHERE situacao_loja='ativa'
          AND data_cadastro_loja >= current_date - interval '60' day
          AND data_cadastro_loja <= current_date
          AND (data_primeira_config_pagamento IS NULL
            OR data_primeira_config_logistica IS NULL
            OR data_primeira_config_produto   IS NULL
            OR (data_primeira_venda IS NULL AND data_cadastro_loja <= current_date - interval '3' day)
            OR (coalesce(vlr_gmv_ultimos_30d,0) = 0 AND data_primeira_venda IS NOT NULL))
    """)
    n_onb = int(rows_onb[0][0]) if rows_onb else 0
except Exception:
    pass

# ── LAYOUT ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='padding:3rem 2.5rem 1.5rem'>
    <div style='display:flex;align-items:center;gap:.8rem;margin-bottom:.3rem'>
        <span style='font-size:28px'>⚡</span>
        <span style='font-size:32px;font-weight:800;color:#D4F53C;letter-spacing:-1px'>X Li</span>
    </div>
    <div style='font-size:14px;color:#9DBDBB'>
        Inteligência de lojistas · Loja Integrada
    </div>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    n_str = f"<div style='font-size:48px;font-weight:800;color:#E24B4A;line-height:1'>{n_onb}</div><div style='font-size:12px;color:#888;margin-bottom:1rem'>lojas em onboarding incompleto</div>" if n_onb is not None else ""
    st.markdown(f"""
    <div style='background:white;border-radius:20px;padding:2rem;margin:0 .5rem 1rem .5rem;min-height:220px'>
        <div style='font-size:13px;font-weight:700;color:#888;text-transform:uppercase;
                    letter-spacing:.08em;margin-bottom:1.2rem'>🚀 Onboarding</div>
        {n_str}
        <div style='font-size:15px;font-weight:700;color:#1A2E2B;margin-bottom:.4rem'>
            Fila de lojas novas
        </div>
        <div style='font-size:13px;color:#5A7A78;line-height:1.7'>
            Gargalo identificado e ação recomendada para cada loja.
            CS vê o que fazer sem precisar diagnosticar.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("🚀 Abrir Onboarding", use_container_width=True, key="btn_onb",
                  type="primary"):
        st.switch_page(onb_path)

with col2:
    st.markdown(f"""
    <div style='background:#1A6A64;border-radius:20px;padding:2rem;margin:0 .5rem 1rem .5rem;min-height:220px'>
        <div style='font-size:13px;font-weight:700;color:#9DBDBB;text-transform:uppercase;
                    letter-spacing:.08em;margin-bottom:1.2rem'>⚡ Raio X</div>
        <div style='font-size:48px;font-weight:800;color:#D4F53C;line-height:1'>Top 100</div>
        <div style='font-size:12px;color:#9DBDBB;margin-bottom:1rem'>melhores lojistas monitorados</div>
        <div style='font-size:15px;font-weight:700;color:white;margin-bottom:.4rem'>
            Top sellers em risco
        </div>
        <div style='font-size:13px;color:#9DBDBB;line-height:1.7'>
            O app identifica automaticamente quem está em queda
            e abre o diagnóstico completo com causa raiz.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("⚡ Abrir Raio X", use_container_width=True, key="btn_raio",
                  type="primary"):
        st.switch_page(raio_path)

# ── Rodapé ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='padding:1.5rem 2.5rem;display:flex;justify-content:space-between;align-items:center'>
    <div style='font-size:12px;color:#5A9A96'>
        Loja Integrada · Time de Automação N2 · 2026
    </div>
    <div style='font-size:12px;color:#5A9A96'>
        raioxli.streamlit.app
    </div>
</div>
""", unsafe_allow_html=True)
