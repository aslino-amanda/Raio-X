import streamlit as st

st.set_page_config(page_title="X Li", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.block-container{padding:1.5rem 2rem 2rem;background:#F2EDE4;}
.main{background:#F2EDE4;}
[data-testid="stSidebarNav"]{display:none;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style='background:#0D4F4A;border-radius:16px;padding:1.2rem 1.8rem;margin-bottom:1.5rem'>
    <div style='font-size:24px;font-weight:700;color:#D4F53C'>⚡ X Li</div>
    <div style='font-size:12px;color:#9DBDBB;margin-top:3px'>Inteligência de lojistas · Loja Integrada</div>
</div>
""", unsafe_allow_html=True)

# Descobre os arquivos de página disponíveis
import os, glob
pages_dir = os.path.join(os.path.dirname(__file__), "pages")
page_files = sorted(glob.glob(os.path.join(pages_dir, "*.py")))

col1, col2 = st.columns(2)

onboarding_page = next((f for f in page_files if "nboarding" in f or "nboarding" in f.lower()), None)
raiox_page      = next((f for f in page_files if "aio" in f.lower()), None)

with col1:
    st.markdown("""
    <div style='background:white;border-radius:14px;padding:2rem;margin-bottom:.5rem'>
        <div style='font-size:32px'>🚀</div>
        <div style='font-size:18px;font-weight:700;color:#1A2E2B;margin:.5rem 0'>Onboarding</div>
        <div style='font-size:13px;color:#5A7A78;line-height:1.7'>
            Fila de lojas novas com gargalo identificado e ação recomendada.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if onboarding_page:
        rel = os.path.relpath(onboarding_page, os.path.dirname(__file__))
        st.page_link(rel, label="🚀 Abrir Onboarding", use_container_width=True)
    else:
        st.warning("Página de Onboarding não encontrada.")

with col2:
    st.markdown("""
    <div style='background:#0D4F4A;border-radius:14px;padding:2rem;margin-bottom:.5rem'>
        <div style='font-size:32px'>⚡</div>
        <div style='font-size:18px;font-weight:700;color:#D4F53C;margin:.5rem 0'>Raio X</div>
        <div style='font-size:13px;color:#9DBDBB;line-height:1.7'>
            Monitoramento dos top sellers. O app identifica quem está em queda automaticamente.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if raiox_page:
        rel = os.path.relpath(raiox_page, os.path.dirname(__file__))
        st.page_link(rel, label="⚡ Abrir Raio X", use_container_width=True)
    else:
        st.warning("Página Raio X não encontrada.")

# Debug — mostra quais arquivos encontrou
with st.expander("🔧 Debug — arquivos encontrados", expanded=False):
    st.write("pages_dir:", pages_dir)
    st.write("arquivos:", page_files)
