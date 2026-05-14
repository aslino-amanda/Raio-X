"""
X Li — Inteligência de Lojistas
Loja Integrada · Time de Automação · 2026
"""

import streamlit as st

st.set_page_config(
    page_title="X Li",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.block-container{padding:1.5rem 2rem 2rem;background:#F2EDE4;}
.main{background:#F2EDE4;}
[data-testid="stSidebarNav"]{display:none;}
.stButton>button{background:#0D4F4A!important;color:#D4F53C!important;
    font-weight:600!important;border:none!important;border-radius:10px!important;}
</style>
""", unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='background:#0D4F4A;border-radius:16px;padding:1.2rem 1.8rem;
            margin-bottom:1.5rem;display:flex;align-items:center;justify-content:space-between'>
    <div>
        <div style='font-size:24px;font-weight:700;color:#D4F53C;letter-spacing:-.5px'>
            ⚡ X Li
        </div>
        <div style='font-size:12px;color:#9DBDBB;margin-top:3px'>
            Inteligência de lojistas · Loja Integrada
        </div>
    </div>
    <div style='display:flex;gap:10px'>
        <a href='/Onboarding' target='_self'
           style='background:#1A6A64;color:#D4F53C;text-decoration:none;
                  border-radius:8px;padding:7px 18px;font-size:13px;font-weight:600'>
            🚀 Onboarding
        </a>
        <a href='/Raio_X' target='_self'
           style='background:#D4F53C;color:#0D4F4A;text-decoration:none;
                  border-radius:8px;padding:7px 18px;font-size:13px;font-weight:600'>
            ⚡ Raio X
        </a>
    </div>
</div>
""", unsafe_allow_html=True)

# ── HOME ──────────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <a href='/Onboarding' target='_self' style='text-decoration:none'>
    <div style='background:white;border-radius:14px;padding:2rem;cursor:pointer;
                border:2px solid transparent;transition:border .2s;height:100%'>
        <div style='font-size:32px;margin-bottom:1rem'>🚀</div>
        <div style='font-size:18px;font-weight:700;color:#1A2E2B;margin-bottom:.5rem'>
            Onboarding
        </div>
        <div style='font-size:13px;color:#5A7A78;line-height:1.7'>
            Fila de lojas novas com gargalo identificado e ação recomendada.
            CS vê o que fazer sem precisar diagnosticar manualmente.
        </div>
        <div style='margin-top:1.2rem;font-size:12px;font-weight:600;color:#0D4F4A'>
            Abrir Onboarding →
        </div>
    </div>
    </a>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <a href='/Raio_X' target='_self' style='text-decoration:none'>
    <div style='background:#0D4F4A;border-radius:14px;padding:2rem;cursor:pointer;height:100%'>
        <div style='font-size:32px;margin-bottom:1rem'>⚡</div>
        <div style='font-size:18px;font-weight:700;color:#D4F53C;margin-bottom:.5rem'>
            Raio X
        </div>
        <div style='font-size:13px;color:#9DBDBB;line-height:1.7'>
            Monitoramento dos top sellers. O app identifica automaticamente
            quem está em queda e abre o diagnóstico completo: causa raiz,
            clientes churned e ação recomendada.
        </div>
        <div style='margin-top:1.2rem;font-size:12px;font-weight:600;color:#D4F53C'>
            Abrir Raio X →
        </div>
    </div>
    </a>
    """, unsafe_allow_html=True)
