"""
X Li — Raio X
Top sellers em risco + diagnóstico completo individual.

Fluxo:
  1. Carrega top 100 lojas por GMV
  2. Roda triagem de tendência semanal (2 queries leves por loja em risco)
  3. Mostra só as lojas com queda 20%+
  4. Clica numa → abre Raio X completo
  5. Busca manual por ID/nome também disponível
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Raio X · X Li", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

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
        <div style='font-size:20px;font-weight:700;color:#D4F53C'>⚡ Raio X</div>
        <div style='font-size:12px;color:#9DBDBB;margin-top:2px'>
            Top sellers em risco · diagnóstico completo
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
    import urllib.request, json as _json
    s   = st.secrets["metabase"]
    key = s.get("api_key", s.get("token",""))
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

if not _ok():
    st.error("Metabase não conectado. Verifique .streamlit/secrets.toml")
    st.stop()

# ── HELPERS ───────────────────────────────────────────────────────────────────
def safe_float(v):
    try:
        import math; f = float(v or 0)
        return 0.0 if math.isnan(f) else f
    except Exception: return 0.0

def safe_int(v):
    try: return int(float(v or 0))
    except Exception: return 0

def fmt_brl(v):
    return f"R${safe_float(v):,.0f}".replace(",","X").replace(".",",").replace("X",".")

def dias_desde(d):
    if not d or str(d) in ("None","nan","NaT",""): return None
    try: return (date.today() - datetime.strptime(str(d)[:10],"%Y-%m-%d").date()).days
    except Exception: return None

def gerar_sparkline(vals, w=80, h=28):
    if not vals or len(vals) < 2:
        return "<span style='color:#ccc;font-size:11px'>—</span>"
    try:
        vmin, vmax = min(vals), max(vals)
        if vmax == vmin: vmax = vmin + 1
        def _x(i): return int(i/(len(vals)-1)*w)
        def _y(v): return int(h-(v-vmin)/(vmax-vmin)*(h-4)-2)
        pts = " ".join(f"{_x(i)},{_y(v)}" for i,v in enumerate(vals))
        cor = "#E24B4A" if vals[-1] < vals[0] else "#1ABCB0"
        seta = "▼" if vals[-1] < vals[-2] else "▲"
        cors = "#E24B4A" if vals[-1] < vals[-2] else "#1ABCB0"
        return (f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
                f'<polyline points="{pts}" fill="none" stroke="{cor}" stroke-width="2"/>'
                f'<circle cx="{_x(len(vals)-1)}" cy="{_y(vals[-1])}" r="3" fill="{cor}"/>'
                f'</svg><span style="color:{cors};font-size:10px;margin-left:2px">{seta}</span>')
    except Exception: return "—"

# ── QUERIES ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def buscar_top_lojas():
    return rodar_sql("""
    WITH cte AS (
        SELECT
            loja_id,
            ROUND(SUM(IF(data_criacao_pedido >= DATE(DATE_TRUNC('MONTH', CURRENT_DATE())), vlr_total, 0)), 2) AS gmv_mes_atual,
            ROUND(SUM(IF(data_criacao_pedido >= DATE(CURRENT_DATE() - INTERVAL 30 DAY), vlr_total, 0)), 2)   AS gmv_30d,
            ROUND(SUM(vlr_total), 2)                                                                          AS gmv_90d,
            COUNT_IF(data_criacao_pedido >= DATE(DATE_TRUNC('MONTH', CURRENT_DATE())))                        AS ped_mes_atual
        FROM analytics_manual.mv_pedido
        WHERE data_criacao_pedido >= DATE(CURRENT_DATE() - INTERVAL 90 DAY)
          AND (integrador IS NULL OR marketplace IS NULL)
          AND flag_aprovado_hist = 1
        GROUP BY loja_id
    ),
    base AS (
        SELECT
            loja_id,
            gmv_mes_atual,
            gmv_30d,
            gmv_90d,
            ped_mes_atual,
            ROUND((gmv_90d - gmv_30d) / 2, 2) AS gmv_media_2m,
            ROUND(gmv_mes_atual / DAY(CURRENT_DATE()) * DAY(LAST_DAY(CURRENT_DATE())), 2) AS gmv_projetado
        FROM cte
        WHERE gmv_90d > 0
    )
    SELECT
        b.loja_id AS conta_id,
        l.nome_loja,
        upper(l.segmento_loja) AS segmento,
        l.tier_loja,
        l.tipo_plano_atual,
        b.gmv_90d,
        b.gmv_mes_atual,
        b.gmv_projetado,
        b.gmv_media_2m,
        b.ped_mes_atual,
        ROUND((b.gmv_projetado - b.gmv_media_2m) / NULLIF(b.gmv_media_2m, 0) * 100, 1) AS var_projetado_pct
    FROM base b
    LEFT JOIN analytics_manual.mv_loja l ON b.loja_id = l.loja_id
    WHERE b.gmv_media_2m >= 10000
    ORDER BY b.gmv_90d DESC
    LIMIT 100
    """)

def buscar_tendencia_semanal(conta_id: int) -> dict:
    """2 queries separadas — evita timeout do CROSS JOIN."""
    sql_at = f"""
    SELECT
        COUNT(DISTINCT A.pedido_venda_id)         AS pedidos_atual,
        ROUND(SUM(A.pedido_venda_valor_total), 2) AS gmv_atual,
        ROUND(AVG(A.pedido_venda_valor_total), 2) AS ticket_atual,
        MIN(DATE(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'))) AS atual_de,
        MAX(DATE(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'))) AS atual_ate
    FROM pedido_tb_pedido_venda A
    INNER JOIN pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id = D.pedido_venda_situacao_id
    WHERE A.conta_id = {conta_id}
      AND DATE(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'))
          >= DATE(CONVERT_TZ(NOW(),'+00:00','America/Sao_Paulo')) - INTERVAL 14 DAY
      AND DATE(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'))
          < DATE(CONVERT_TZ(NOW(),'+00:00','America/Sao_Paulo'))
      AND D.pedido_venda_situacao_nome != 'Pedido Cancelado'
    """
    sql_ant = f"""
    SELECT
        COUNT(DISTINCT A.pedido_venda_id)         AS pedidos_anterior,
        ROUND(SUM(A.pedido_venda_valor_total), 2) AS gmv_anterior,
        ROUND(AVG(A.pedido_venda_valor_total), 2) AS ticket_anterior,
        MIN(DATE(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'))) AS ref_de,
        MAX(DATE(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'))) AS ref_ate
    FROM pedido_tb_pedido_venda A
    INNER JOIN pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id = D.pedido_venda_situacao_id
    WHERE A.conta_id = {conta_id}
      AND DATE(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'))
          >= DATE(CONVERT_TZ(NOW(),'+00:00','America/Sao_Paulo')) - INTERVAL 44 DAY
      AND DATE(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'))
          < DATE(CONVERT_TZ(NOW(),'+00:00','America/Sao_Paulo')) - INTERVAL 30 DAY
      AND D.pedido_venda_situacao_nome != 'Pedido Cancelado'
    """
    try:
        at  = rodar_sql(sql_at)
        ant = rodar_sql(sql_ant)
    except Exception: return {}
    if at.empty or ant.empty: return {}
    a = at.iloc[0]; p = ant.iloc[0]
    def _v(n,v): return round((n-v)/v*100,1) if v else 0.0
    ga = safe_float(a.get("gmv_atual")); gp = safe_float(p.get("gmv_anterior"))
    pa = safe_float(a.get("pedidos_atual")); pp = safe_float(p.get("pedidos_anterior"))
    ta = safe_float(a.get("ticket_atual")); tp = safe_float(p.get("ticket_anterior"))
    return {
        "gmv_atual": ga, "gmv_anterior": gp,
        "pedidos_atual": pa, "pedidos_anterior": pp,
        "ticket_atual": ta, "ticket_anterior": tp,
        "var_gmv_pct": _v(ga,gp), "var_pedidos_pct": _v(pa,pp), "var_ticket_pct": _v(ta,tp),
        "gmv_em_risco": round(gp-ga,2) if gp > ga else 0.0,
        "atual_de": str(a.get("atual_de","")), "atual_ate": str(a.get("atual_ate","")),
        "ref_de": str(p.get("ref_de","")), "ref_ate": str(p.get("ref_ate","")),
    }

def buscar_historico_mensal(conta_id: int) -> list:
    try:
        df = rodar_sql(f"""
        SELECT
            DATE_FORMAT(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'),'%Y-%m') AS mes,
            ROUND(SUM(A.pedido_venda_valor_total),2) AS gmv
        FROM pedido_tb_pedido_venda A
        INNER JOIN pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id=D.pedido_venda_situacao_id
        WHERE A.conta_id={conta_id}
          AND CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo')
              >= DATE_FORMAT(DATE_SUB(NOW(),INTERVAL 6 MONTH),'%Y-%m-01')
          AND D.pedido_venda_situacao_nome != 'Pedido Cancelado'
        GROUP BY mes ORDER BY mes ASC
        """)
        return df["gmv"].tolist() if not df.empty else []
    except Exception: return []

def buscar_mix_pagamento(conta_id: int) -> pd.DataFrame:
    try:
        return rodar_sql(f"""
        SELECT
            DATE_FORMAT(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'),'%Y-%m') AS mes,
            F.pagamento_nome AS forma_pagamento,
            COUNT(DISTINCT A.pedido_venda_id) AS total_pedidos,
            ROUND(AVG(A.pedido_venda_valor_total),2) AS ticket_medio
        FROM pedido_tb_pedido_venda A
        INNER JOIN pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id=D.pedido_venda_situacao_id
        INNER JOIN pedido_tb_pedido_venda_pagamento E ON A.pedido_venda_id=E.pedido_venda_id
        INNER JOIN configuracao_tb_pagamento F ON E.pagamento_id=F.pagamento_id
        WHERE A.conta_id={conta_id}
          AND CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo')
              >= DATE_FORMAT(DATE_SUB(NOW(),INTERVAL 6 MONTH),'%Y-%m-01')
          AND D.pedido_venda_situacao_nome != 'Pedido Cancelado'
        GROUP BY mes, forma_pagamento ORDER BY mes ASC, total_pedidos DESC
        """)
    except Exception: return pd.DataFrame()

def buscar_novos_recorrentes(conta_id: int) -> pd.DataFrame:
    try:
        return rodar_sql(f"""
        SELECT
            DATE_FORMAT(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'),'%Y-%m') AS mes,
            CASE WHEN B.cliente_data_criacao >= DATE_FORMAT(
                CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo'),'%Y-%m-01')
            THEN 'Novo' ELSE 'Recorrente' END AS tipo_cliente,
            COUNT(DISTINCT A.pedido_venda_id) AS total_pedidos,
            ROUND(SUM(A.pedido_venda_valor_total),2) AS receita,
            ROUND(AVG(A.pedido_venda_valor_total),2) AS ticket_medio
        FROM pedido_tb_pedido_venda A
        INNER JOIN cliente_tb_cliente B ON A.cliente_id=B.cliente_id
        INNER JOIN pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id=D.pedido_venda_situacao_id
        WHERE A.conta_id={conta_id}
          AND CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo')
              >= DATE_FORMAT(DATE_SUB(NOW(),INTERVAL 6 MONTH),'%Y-%m-01')
          AND D.pedido_venda_situacao_nome != 'Pedido Cancelado'
        GROUP BY mes, tipo_cliente ORDER BY mes ASC
        """)
    except Exception: return pd.DataFrame()

def buscar_churned(conta_id: int) -> pd.DataFrame:
    hoje = date.today()
    ref_ini = (hoje - relativedelta(months=5)).strftime("%Y-%m-01")
    ref_fim = (hoje - relativedelta(months=4)).strftime("%Y-%m-28")
    corte   = (hoje - relativedelta(months=2)).strftime("%Y-%m-01")
    try:
        return rodar_sql(f"""
        SELECT B.cliente_id, B.cliente_nome, B.cliente_email,
            COUNT(DISTINCT A.pedido_venda_id) AS total_pedidos,
            ROUND(SUM(A.pedido_venda_valor_total),2) AS receita_historico,
            ROUND(AVG(A.pedido_venda_valor_total),2) AS ticket_medio,
            MAX(CONVERT_TZ(A.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo')) AS ultimo_pedido
        FROM cliente_tb_cliente B
        INNER JOIN pedido_tb_pedido_venda A ON B.cliente_id=A.cliente_id
        INNER JOIN pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id=D.pedido_venda_situacao_id
        WHERE A.conta_id={conta_id}
          AND D.pedido_venda_situacao_nome != 'Pedido Cancelado'
          AND B.cliente_id IN (
            SELECT DISTINCT A2.cliente_id FROM pedido_tb_pedido_venda A2
            INNER JOIN pedido_tb_pedido_venda_situacao D2 ON A2.pedido_venda_situacao_id=D2.pedido_venda_situacao_id
            WHERE A2.conta_id={conta_id}
              AND CONVERT_TZ(A2.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo')
                  BETWEEN '{ref_ini}' AND '{ref_fim}'
              AND D2.pedido_venda_situacao_nome != 'Pedido Cancelado'
          )
          AND B.cliente_id NOT IN (
            SELECT DISTINCT A3.cliente_id FROM pedido_tb_pedido_venda A3
            INNER JOIN pedido_tb_pedido_venda_situacao D3 ON A3.pedido_venda_situacao_id=D3.pedido_venda_situacao_id
            WHERE A3.conta_id={conta_id}
              AND CONVERT_TZ(A3.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo') >= '{corte}'
              AND D3.pedido_venda_situacao_nome != 'Pedido Cancelado'
          )
        GROUP BY B.cliente_id, B.cliente_nome, B.cliente_email
        ORDER BY receita_historico DESC LIMIT 20
        """)
    except Exception: return pd.DataFrame()

def buscar_loja(loja_id: int) -> dict:
    try:
        df = rodar_sql(f"""
        SELECT loja_id,
            COALESCE(upper(nome_loja),upper(dominio_loja),CAST(loja_id AS CHAR)) AS nome_loja,
            dominio_loja, email_loja,
            upper(segmento_loja) AS segmento_loja, upper(situacao_loja) AS situacao_loja,
            data_cadastro_loja,
            upper(cidade_endereco_loja) AS cidade, upper(estado_endereco_loja) AS estado,
            CASE WHEN aquisicao_utm_source IS NULL THEN 'ORGÂNICO' ELSE 'PAGO' END AS origem,
            data_primeira_config_pagamento, data_primeira_config_logistica,
            data_primeira_config_produto, data_ini_plano_atual,
            upper(tipo_plano_atual) AS tipo_plano, vlr_plano_mrr_atual,
            CASE WHEN data_ini_plano_atual IS NOT NULL THEN 'PAGO' ELSE 'GRÁTIS' END AS status_plano,
            data_primeira_visita, qtde_visitas_ultimos_30d,
            data_primeira_venda, qtd_pedido_ultimos_30d, vlr_gmv_ultimos_30d,
            CASE
                WHEN data_primeira_config_pagamento IS NULL
                  OR data_primeira_config_logistica IS NULL
                  OR data_primeira_config_produto   IS NULL THEN 'ONBOARDING INCOMPLETO'
                WHEN data_primeira_venda IS NULL THEN 'NUNCA VENDEU'
                WHEN coalesce(vlr_gmv_ultimos_30d,0) = 0 THEN 'SEM VENDAS RECENTES'
                ELSE 'LOJA ATIVA'
            END AS status_loja
        FROM analytics_manual.mv_loja
        WHERE loja_id = {loja_id} LIMIT 1
        """)
        return df.iloc[0].to_dict() if not df.empty else {}
    except Exception: return {}

# ════════════════════════════════════════════════════════════════════════════════
# ESTADO — loja selecionada para Raio X completo
# ════════════════════════════════════════════════════════════════════════════════
if "rx_loja_id" not in st.session_state:
    st.session_state.rx_loja_id = None

# ── BUSCA MANUAL ──────────────────────────────────────────────────────────────
col_inp, col_btn = st.columns([5,1])
with col_inp:
    busca = st.text_input("", placeholder="🔍  Buscar loja por ID ou nome para Raio X manual",
                          label_visibility="collapsed")
with col_btn:
    if st.button("Analisar", use_container_width=True):
        if busca.strip().isdigit():
            st.session_state.rx_loja_id = int(busca.strip())
        elif busca.strip():
            try:
                df_b = rodar_sql(f"""
                    SELECT loja_id, upper(nome_loja) AS nome_loja, upper(segmento_loja) AS segmento_loja
                    FROM analytics_manual.mv_loja
                    WHERE upper(nome_loja) LIKE upper('%{busca.strip()}%') LIMIT 10
                """)
                if not df_b.empty:
                    if len(df_b) == 1:
                        st.session_state.rx_loja_id = int(df_b.iloc[0]["loja_id"])
                    else:
                        ops = {f"{r['loja_id']} — {r['nome_loja']}": int(r["loja_id"]) for _,r in df_b.iterrows()}
                        sel = st.selectbox("Selecione a loja:", list(ops.keys()))
                        st.session_state.rx_loja_id = ops[sel]
            except Exception as e:
                st.warning(f"Erro na busca: {e}")

# ════════════════════════════════════════════════════════════════════════════════
# RAIO X COMPLETO — loja selecionada
# ════════════════════════════════════════════════════════════════════════════════
if st.session_state.rx_loja_id:
    lid = st.session_state.rx_loja_id

    col_titulo, col_fechar = st.columns([6,1])
    with col_titulo:
        st.markdown(f"<div style='font-size:16px;font-weight:700;color:#0D4F4A;margin:.5rem 0'>⚡ Raio X — Loja {lid}</div>", unsafe_allow_html=True)
    with col_fechar:
        if st.button("✕ Fechar", use_container_width=True):
            st.session_state.rx_loja_id = None
            st.rerun()

    with st.spinner("Carregando diagnóstico completo..."):
        loja      = buscar_loja(lid)
        tend      = buscar_tendencia_semanal(lid)
        hist      = buscar_historico_mensal(lid)
        df_pag    = buscar_mix_pagamento(lid)
        df_nr     = buscar_novos_recorrentes(lid)
        df_ch     = buscar_churned(lid)

    if not loja:
        st.error(f"Loja {lid} não encontrada.")
        st.session_state.rx_loja_id = None
        st.stop()

    nome        = str(loja.get("nome_loja", f"Loja {lid}"))
    segmento    = str(loja.get("segmento_loja","—"))
    status_loja = str(loja.get("status_loja","—"))
    status_plano= str(loja.get("status_plano","GRÁTIS"))
    email_loja  = str(loja.get("email_loja","—"))
    cidade      = str(loja.get("cidade","—"))
    estado      = str(loja.get("estado","—"))
    origem      = str(loja.get("origem","—"))
    dias_cad    = dias_desde(loja.get("data_cadastro_loja")) or 0

    # Calcula variação de GMV
    var_gmv = None
    if tend and tend.get("gmv_anterior"):
        var_gmv = safe_float(tend.get("var_gmv_pct")) / 100

    # Status real considerando queda
    if status_loja == "LOJA ATIVA" and var_gmv is not None:
        if var_gmv <= -0.50:   status_real = "QUEDA CRÍTICA";  cor_st = "#991B1B"; bg_st = "#FEF2F2"
        elif var_gmv <= -0.30: status_real = "QUEDA ALTA";     cor_st = "#991B1B"; bg_st = "#FEF2F2"
        elif var_gmv <= -0.20: status_real = "QUEDA EM RISCO"; cor_st = "#92400E"; bg_st = "#FFFBEB"
        else:                  status_real = "LOJA ATIVA";     cor_st = "#0D4F4A"; bg_st = "#D1FAF6"
    else:
        status_real = status_loja
        cor_st = "#991B1B" if status_loja in ("ONBOARDING INCOMPLETO","SEM VENDAS RECENTES") else "#92400E" if status_loja == "NUNCA VENDEU" else "#0D4F4A"
        bg_st  = "#FEF2F2" if status_loja in ("ONBOARDING INCOMPLETO","SEM VENDAS RECENTES") else "#FFFBEB" if status_loja == "NUNCA VENDEU" else "#D1FAF6"

    # Score
    if var_gmv is not None and var_gmv <= -0.50:   score = 85
    elif var_gmv is not None and var_gmv <= -0.30: score = 70
    elif var_gmv is not None and var_gmv <= -0.20: score = 55
    elif status_loja == "ONBOARDING INCOMPLETO":   score = 70 if dias_cad >= 7 else 50
    elif status_loja == "NUNCA VENDEU":            score = 45 if dias_cad >= 20 else 25
    elif status_loja == "SEM VENDAS RECENTES":     score = 55
    else:                                           score = 5
    if status_plano == "PAGO" and score >= 35:     score = min(score + 10, 100)

    cor_score = "#E24B4A" if score >= 70 else "#F59E0B" if score >= 40 else "#1ABCB0"

    st.markdown("<div style='background:white;border-radius:14px;padding:1rem 1.5rem;margin-bottom:1rem'>", unsafe_allow_html=True)
    col_info, col_sc = st.columns([5,1])
    with col_info:
        st.markdown(
            f"<div style='font-size:20px;font-weight:700;color:#1A2E2B'>{nome}</div>"
            f"<div style='font-size:12px;color:#888;margin-top:3px'>ID {lid} · {segmento} · {cidade}/{estado} · {email_loja}</div>"
            f"<div style='margin-top:8px;display:flex;gap:6px;flex-wrap:wrap'>"
            f"<span style='background:{bg_st};color:{cor_st};padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600'>{status_real}</span>"
            f"<span style='background:#EEEDFE;color:#3C3489;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600'>{status_plano}</span>"
            f"<span style='background:#F2EDE4;color:#5A7A78;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600'>{origem} · {dias_cad}d</span>"
            f"</div>",
            unsafe_allow_html=True)
    with col_sc:
        st.markdown(
            f"<div style='text-align:right'>"
            f"<div style='font-size:40px;font-weight:800;color:{cor_score}'>{score}</div>"
            f"<div style='font-size:11px;color:#888'>score de risco</div>"
            f"</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── LINHA DO TEMPO ────────────────────────────────────────────────────────
    st.markdown("#### 📅 Linha do tempo")
    marcos = [
        ("Cadastro",         loja.get("data_cadastro_loja"),            "#0D4F4A", "✅"),
        ("1ª config. pag.",  loja.get("data_primeira_config_pagamento"), "#1ABCB0", "💳"),
        ("1ª config. frete", loja.get("data_primeira_config_logistica"), "#1ABCB0", "📦"),
        ("1ª config. prod.", loja.get("data_primeira_config_produto"),   "#1ABCB0", "🛍️"),
        ("1ª visita",        loja.get("data_primeira_visita"),           "#6366F1", "👁️"),
        ("1ª venda",         loja.get("data_primeira_venda"),            "#D4F53C", "🎉"),
    ]
    cols_tl = st.columns(6)
    for col, (label, data, cor, emoji) in zip(cols_tl, marcos):
        with col:
            if data and str(data) not in ("None","nan","NaT",""):
                d = dias_desde(data) or 0
                st.markdown(
                    f"<div style='background:{cor};border-radius:10px;padding:.6rem;text-align:center'>"
                    f"<div style='font-size:16px'>{emoji}</div>"
                    f"<div style='font-size:10px;font-weight:700;color:{'#1A2E2B' if cor=='#D4F53C' else 'white'};margin-top:3px'>{label}</div>"
                    f"<div style='font-size:9px;color:{'#444' if cor=='#D4F53C' else '#9DBDBB'}'>{str(data)[:10]}</div>"
                    f"<div style='font-size:9px;color:{'#444' if cor=='#D4F53C' else '#9DBDBB'}'>{d}d atrás</div>"
                    f"</div>", unsafe_allow_html=True)
            else:
                st.markdown(
                    f"<div style='background:#F5F2EE;border-radius:10px;padding:.6rem;text-align:center;border:1px dashed #C8C0B4'>"
                    f"<div style='font-size:16px;opacity:.3'>{emoji}</div>"
                    f"<div style='font-size:10px;color:#AAA;margin-top:3px'>{label}</div>"
                    f"<div style='font-size:9px;color:#CCC'>não realizado</div>"
                    f"</div>", unsafe_allow_html=True)

    st.divider()

    # ── SCORE 4 DIMENSÕES ─────────────────────────────────────────────────────
    st.markdown("#### 📊 Score de saúde")
    tem_prod = str(loja.get("data_primeira_config_produto","")) not in ("","None","nan","NaT")
    tem_pag  = str(loja.get("data_primeira_config_pagamento","")) not in ("","None","nan","NaT")
    tem_log  = str(loja.get("data_primeira_config_logistica","")) not in ("","None","nan","NaT")
    visitas  = safe_int(loja.get("qtde_visitas_ultimos_30d"))
    pedidos  = safe_int(loja.get("qtd_pedido_ultimos_30d"))
    tem_venda= str(loja.get("data_primeira_venda","")) not in ("","None","nan","NaT")

    s_cfg  = (int(tem_prod)+int(tem_pag)+int(tem_log))/3*100
    s_traf = min(100, visitas/10)
    s_conv = 100 if (tem_venda and pedidos > 0) else 50 if tem_venda else 0
    s_ret  = max(0, min(100, 60 + (var_gmv or 0)*100)) if var_gmv is not None else (60 if tem_venda and pedidos > 0 else 20 if tem_venda else 0)

    dims = [("Configuração",s_cfg,"Prod+Pag+Frete","#0D4F4A"),
            ("Tráfego",s_traf,f"{visitas} visitas/30d","#6366F1"),
            ("Conversão",s_conv,f"{pedidos} pedidos/30d","#F59E0B"),
            ("Retenção",s_ret,"Tendência semanal","#E24B4A" if s_ret < 40 else "#1ABCB0")]
    cd = st.columns(4)
    for col,(nome_d,sv,sub,cor_d) in zip(cd,dims):
        with col:
            c_s = cor_d if sv >= 50 else "#E24B4A"
            st.markdown(
                f"<div style='background:white;border-radius:12px;padding:1rem;text-align:center'>"
                f"<div style='font-size:13px;font-weight:700;color:#1A2E2B;margin-bottom:.4rem'>{nome_d}</div>"
                f"<div style='font-size:34px;font-weight:800;color:{c_s}'>{sv:.0f}</div>"
                f"<div style='background:#F2EDE4;border-radius:4px;height:5px;margin:.4rem 0'>"
                f"<div style='background:{c_s};width:{min(sv,100):.0f}%;height:5px;border-radius:4px'></div></div>"
                f"<div style='font-size:11px;color:#888'>{sub}</div>"
                f"</div>", unsafe_allow_html=True)

    st.divider()

    # ── TENDÊNCIA SEMANAL ─────────────────────────────────────────────────────
    st.markdown("#### 📉 Tendência de GMV — últimas 2 semanas vs mesmo período 30 dias atrás")
    if tend and tend.get("gmv_anterior"):
        st.caption(f"Atual: {tend.get('atual_de','')} → {tend.get('atual_ate','')} | Ref: {tend.get('ref_de','')} → {tend.get('ref_ate','')}")
        mt = st.columns(4)
        for col,(label,val,var) in zip(mt,[
            ("GMV atual",       fmt_brl(tend.get("gmv_atual")),    tend.get("var_gmv_pct")),
            ("Pedidos",         str(safe_int(tend.get("pedidos_atual"))), tend.get("var_pedidos_pct")),
            ("Ticket médio",    fmt_brl(tend.get("ticket_atual")), tend.get("var_ticket_pct")),
            ("GMV em risco",    fmt_brl(tend.get("gmv_em_risco")), None),
        ]):
            with col:
                if var is not None:
                    c = "#E24B4A" if float(var) < 0 else "#1ABCB0"
                    s = "+" if float(var) > 0 else ""
                    var_str = f"<span style='color:{c};font-weight:700'>{s}{float(var):.1f}%</span>"
                else:
                    cr = "#E24B4A" if safe_float(tend.get("gmv_em_risco")) > 0 else "#1ABCB0"
                    var_str = f"<span style='color:{cr};font-weight:700'>vs referência</span>"
                st.markdown(
                    f"<div style='background:white;border-radius:10px;padding:.8rem'>"
                    f"<div style='font-size:11px;color:#888;text-transform:uppercase'>{label}</div>"
                    f"<div style='font-size:20px;font-weight:700;color:#1A2E2B'>{val}</div>"
                    f"<div style='font-size:12px;margin-top:2px'>{var_str}</div>"
                    f"</div>", unsafe_allow_html=True)

        # Causa raiz automática
        var_g = safe_float(tend.get("var_gmv_pct"))
        var_p = safe_float(tend.get("var_pedidos_pct"))
        var_t = safe_float(tend.get("var_ticket_pct"))
        causas = []
        if var_p <= -20 and abs(var_t) < 10:
            causas.append(f"📉 Volume de pedidos caiu {abs(var_p):.0f}% com ticket estável — queda de tráfego ou conversão")
        if var_t <= -15 and var_p >= -10:
            causas.append(f"🏷️ Ticket médio caiu {abs(var_t):.0f}% mantendo volume — verificar cupons ou reprecificação")
        if var_p <= -20 and var_t <= -10:
            causas.append(f"🔴 Queda combinada: {abs(var_p):.0f}% em pedidos e {abs(var_t):.0f}% no ticket — investigar mix e pagamento")
        if causas:
            st.markdown(
                f"<div style='background:#FEF2F2;border-left:4px solid #E24B4A;border-radius:8px;"
                f"padding:.8rem 1rem;margin-top:.8rem'>"
                f"<div style='font-size:12px;font-weight:700;color:#991B1B'>Causa raiz detectada</div>"
                + "".join(f"<div style='font-size:13px;color:#333;margin-top:4px'>→ {c}</div>" for c in causas)
                + "</div>", unsafe_allow_html=True)
    else:
        st.info("Histórico semanal insuficiente para calcular tendência.")

    # Sparkline histórico
    if hist:
        st.markdown("**Histórico GMV — últimos 6 meses**")
        st.markdown(
            f"<div style='background:white;border-radius:10px;padding:.8rem 1rem;display:inline-block'>"
            f"{gerar_sparkline(hist, w=200, h=40)}</div>", unsafe_allow_html=True)

    st.divider()

    # ── MIX DE PAGAMENTO ──────────────────────────────────────────────────────
    if not df_pag.empty and "mes" in df_pag.columns:
        st.markdown("#### 💳 Mix de pagamento")
        df_pag["total_pedidos"] = pd.to_numeric(df_pag["total_pedidos"], errors="coerce").fillna(0)

        # Alerta de forma removida
        meses_s = sorted(df_pag["mes"].unique())
        if len(meses_s) >= 2:
            formas_rec = set(df_pag[df_pag["mes"]==meses_s[-1]]["forma_pagamento"].tolist())
            formas_ant = set(df_pag[df_pag["mes"]==meses_s[-2]]["forma_pagamento"].tolist())
            removidas  = formas_ant - formas_rec
            criticas   = [f for f in removidas if any(k in str(f).upper() for k in ["PIX","CART","CRED","DEBIT"])]
            if criticas:
                st.markdown(
                    f"<div style='background:#FEF2F2;border-left:4px solid #E24B4A;border-radius:8px;"
                    f"padding:.7rem 1rem;margin-bottom:.8rem'>"
                    f"<div style='font-size:13px;font-weight:700;color:#991B1B'>⚠️ Forma crítica removida: {', '.join(criticas)}</div>"
                    f"</div>", unsafe_allow_html=True)

        try:
            piv = df_pag.pivot_table(index="forma_pagamento", columns="mes",
                                     values="total_pedidos", aggfunc="sum", fill_value=0).reset_index()
            piv.columns.name = None
            st.dataframe(piv, use_container_width=True, hide_index=True)
        except Exception:
            st.dataframe(df_pag[["mes","forma_pagamento","total_pedidos","ticket_medio"]],
                         use_container_width=True, hide_index=True)
        st.divider()

    # ── NOVOS VS RECORRENTES ──────────────────────────────────────────────────
    if not df_nr.empty:
        st.markdown("#### 👥 Novos vs. recorrentes")
        df_nr["receita"] = pd.to_numeric(df_nr.get("receita", df_nr["total_pedidos"]), errors="coerce").fillna(0)

        # Alerta de queda de recorrentes
        rec = df_nr[df_nr["tipo_cliente"]=="Recorrente"].sort_values("mes")
        if len(rec) >= 2:
            r0 = safe_float(rec["receita"].iloc[0])
            r1 = safe_float(rec["receita"].iloc[-1])
            if r0 > 0 and (r1-r0)/r0 <= -0.40:
                st.markdown(
                    f"<div style='background:#FEF2F2;border-left:4px solid #E24B4A;border-radius:8px;"
                    f"padding:.7rem 1rem;margin-bottom:.8rem'>"
                    f"<div style='font-size:13px;font-weight:700;color:#991B1B'>"
                    f"🔴 Receita de recorrentes caiu {abs((r1-r0)/r0)*100:.0f}% no período — sinal de churn B2B</div>"
                    f"</div>", unsafe_allow_html=True)

        st.dataframe(
            df_nr[["mes","tipo_cliente","total_pedidos","receita","ticket_medio"]].rename(columns={
                "mes":"Mês","tipo_cliente":"Tipo","total_pedidos":"Pedidos",
                "receita":"Receita","ticket_medio":"Ticket"}),
            use_container_width=True, hide_index=True)
        st.divider()

    # ── CLIENTES CHURNED ──────────────────────────────────────────────────────
    if not df_ch.empty:
        receita_risco = safe_float(df_ch["receita_historico"].sum()) if "receita_historico" in df_ch.columns else 0
        st.markdown(f"#### ⚠️ Clientes que sumiram — {len(df_ch)} identificados")
        st.markdown(
            f"<div style='background:#FEF2F2;border-left:4px solid #E24B4A;border-radius:8px;"
            f"padding:.8rem 1rem;margin-bottom:.8rem'>"
            f"<div style='font-size:14px;font-weight:700;color:#991B1B'>"
            f"💰 {fmt_brl(receita_risco)} em receita histórica em risco</div>"
            f"<div style='font-size:12px;color:#666;margin-top:3px'>"
            f"Clientes ativos no período de referência que pararam de comprar.</div>"
            f"</div>", unsafe_allow_html=True)
        cols_ch = [c for c in ["cliente_nome","cliente_email","total_pedidos",
                                "receita_historico","ticket_medio","ultimo_pedido"] if c in df_ch.columns]
        df_show = df_ch[cols_ch].copy()
        if "receita_historico" in df_show: df_show["receita_historico"] = df_show["receita_historico"].apply(fmt_brl)
        if "ticket_medio"      in df_show: df_show["ticket_medio"]      = df_show["ticket_medio"].apply(fmt_brl)
        st.dataframe(df_show, use_container_width=True, hide_index=True)
        st.divider()

    # ── AÇÃO RECOMENDADA ──────────────────────────────────────────────────────
    st.markdown("#### 🎯 Ação recomendada")
    tab_n2, tab_cs, tab_lider = st.tabs(["🔧 N2 · Automação","📞 CS · Sucesso do Cliente","📊 Liderança"])

    with tab_n2:
        if tend and tend.get("gmv_anterior"):
            c1,c2,c3 = st.columns(3)
            c1.metric("Var. GMV",     f"{safe_float(tend.get('var_gmv_pct')):+.1f}%")
            c2.metric("Var. Pedidos", f"{safe_float(tend.get('var_pedidos_pct')):+.1f}%")
            c3.metric("Var. Ticket",  f"{safe_float(tend.get('var_ticket_pct')):+.1f}%")
        acao_tecnica = {
            "QUEDA CRÍTICA":         "Diagnóstico completo urgente — mix de pagamento, churn B2B, variação de cupom",
            "QUEDA ALTA":            "Verificar mix de pagamento e clientes recorrentes de alto valor",
            "QUEDA EM RISCO":        "Monitorar tendência por mais 7 dias — preparar diagnóstico se persistir",
            "ONBOARDING INCOMPLETO": "Identificar gargalo específico e acionar automação de e-mail",
            "NUNCA VENDEU":          "Verificar visitas e taxa de conversão — problema de tráfego ou produto",
            "SEM VENDAS RECENTES":   "CS verificar urgente: loja acessível, estoque ativo, domínio válido",
        }.get(status_real, "Monitoramento de rotina")
        st.markdown(f"→ {acao_tecnica}")

    with tab_cs:
        acao_cs = {
            "QUEDA CRÍTICA":         "Contato direto (WhatsApp ou telefone) — não usar e-mail genérico. Verificar se houve ruptura no atendimento ou produto e oferecer condição especial.",
            "QUEDA ALTA":            "Ligar para os principais clientes recorrentes — verificar se seguem comprando e o motivo da queda.",
            "QUEDA EM RISCO":        "Monitorar de perto. Se queda persistir na próxima semana, acionar contato direto.",
            "ONBOARDING INCOMPLETO": "Entrar em contato para ajudar a completar os passos que faltam.",
            "NUNCA VENDEU":          "Oferecer suporte para divulgação e primeiros pedidos.",
            "SEM VENDAS RECENTES":   "Verificar o que mudou e oferecer reativação com condição especial.",
        }.get(status_real, "Monitoramento de rotina — sem ação necessária.")
        st.markdown(f"**Situação:** {status_real}")
        st.markdown(f"→ {acao_cs}")
        if not df_ch.empty:
            st.markdown(f"→ Contatar os **{min(5,len(df_ch))} principais clientes churned** listados acima via WhatsApp ou telefone — não e-mail marketing.")

    with tab_lider:
        lc1,lc2,lc3 = st.columns(3)
        lc1.metric("GMV 30d", fmt_brl(loja.get("vlr_gmv_ultimos_30d")))
        lc2.metric("Pedidos 30d", str(safe_int(loja.get("qtd_pedido_ultimos_30d"))))
        lc3.metric("Var. GMV semanal", f"{safe_float(tend.get('var_gmv_pct')):+.1f}%" if tend and tend.get("gmv_anterior") else "—")
        if receita_risco := (safe_float(df_ch["receita_historico"].sum()) if not df_ch.empty and "receita_historico" in df_ch.columns else 0):
            st.metric("Receita em risco (churned)", fmt_brl(receita_risco))

    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
    st.stop()


# ════════════════════════════════════════════════════════════════════════════════
# PAINEL PRINCIPAL — top sellers em risco
# ════════════════════════════════════════════════════════════════════════════════
with st.spinner("Carregando top sellers..."):
    try:
        df_top = buscar_top_lojas()
    except Exception as e:
        st.error(f"Erro ao carregar top sellers: {e}")
        st.stop()

if df_top.empty:
    st.info("Nenhum dado de top sellers disponível.")
    st.stop()

df_top["var_projetado_pct"] = pd.to_numeric(df_top["var_projetado_pct"], errors="coerce")
df_risco = df_top[df_top["var_projetado_pct"] <= -20].copy()
df_risco["gmv_em_risco"] = (
    pd.to_numeric(df_risco["gmv_media_2m"], errors="coerce") -
    pd.to_numeric(df_risco["gmv_projetado"], errors="coerce")
).clip(lower=0).round(2)

n_risco   = len(df_risco)
n_critico = len(df_top[df_top["var_projetado_pct"] <= -50])
n_atencao = len(df_top[(df_top["var_projetado_pct"] > -50) & (df_top["var_projetado_pct"] <= -20)])
n_ok      = len(df_top[df_top["var_projetado_pct"] > -20])
gmv_total_risco = max(0,
    pd.to_numeric(df_risco["gmv_media_2m"], errors="coerce").fillna(0).sum() -
    pd.to_numeric(df_risco["gmv_projetado"], errors="coerce").fillna(0).sum()
)

# Banner de risco
st.markdown(f"""
<div style='background:#0D4F4A;border-radius:12px;padding:1rem 1.5rem;margin-bottom:1rem;
            display:flex;justify-content:space-between;align-items:center'>
    <div>
        <div style='font-size:11px;color:#9DCFCC;text-transform:uppercase;letter-spacing:.1em'>
            GMV em risco este mês
        </div>
        <div style='font-size:28px;font-weight:800;color:#D4F53C'>{fmt_brl(gmv_total_risco)}</div>
        <div style='font-size:12px;color:#9DCFCC;margin-top:2px'>
            em {n_risco} loja(s) com queda detectada · de {len(df_top)} monitoradas
        </div>
    </div>
    <div style='text-align:right'>
        <div style='font-size:14px;color:white'>
            🔴 {n_critico} crítico &nbsp;·&nbsp; 🟡 {n_atencao} risco &nbsp;·&nbsp; 🟢 {n_ok} OK
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if n_risco == 0:
    st.markdown("""
    <div style='background:#F0FDF4;border:1px solid #86EFAC;border-radius:10px;
                padding:1rem;font-size:13px;color:#166534;text-align:center'>
        ✅ Nenhum top seller com queda de 20%+ hoje.
    </div>
    """, unsafe_allow_html=True)
    st.stop()

st.markdown(f"**{n_risco} loja(s) em risco — clique em ⚡ Raio X para diagnóstico completo**")
dia_atual = date.today().day

for _, r in df_risco.sort_values("var_projetado_pct").iterrows():
    lid      = int(r["conta_id"])
    nome_r   = str(r.get("nome_loja","—"))
    var_v    = float(r["var_projetado_pct"])
    cor_v    = "#E24B4A" if var_v <= -50 else "#F59E0B"
    gmv_r    = safe_float(r["gmv_em_risco"])
    hist_r   = buscar_historico_mensal(lid)
    spark    = gerar_sparkline(hist_r)

    with st.container():
        col_info, col_metr, col_spark, col_btn = st.columns([3, 2, 1.5, 1])

        with col_info:
            st.markdown(
                f"<div style='background:white;border-radius:10px;padding:.8rem 1rem;height:100%'>"
                f"<div style='font-size:13px;font-weight:700;color:#1A2E2B'>{nome_r}</div>"
                f"<div style='font-size:11px;color:#888;margin-top:2px'>ID {lid} · {r.get('segmento','—')}</div>"
                f"<div style='font-size:11px;color:#888'>Tier: {r.get('tier_loja','—')} · {r.get('tipo_plano_atual','—')}</div>"
                f"</div>", unsafe_allow_html=True)

        with col_metr:
            st.markdown(
                f"<div style='background:white;border-radius:10px;padding:.8rem 1rem;height:100%'>"
                f"<div style='font-size:11px;color:#888'>Média 2m (d1-{dia_atual})</div>"
                f"<div style='font-size:13px;font-weight:600;color:#1A2E2B'>{fmt_brl(r['gmv_media_2m'])}</div>"
                f"<div style='font-size:11px;color:#888;margin-top:4px'>Projetado este mês</div>"
                f"<div style='font-size:13px;font-weight:600;color:#1A2E2B'>{fmt_brl(r['gmv_projetado'])}</div>"
                f"<div style='font-size:12px;font-weight:700;color:{cor_v};margin-top:4px'>"
                f"{var_v:.0f}% · {fmt_brl(gmv_r)} em risco</div>"
                f"</div>", unsafe_allow_html=True)

        with col_spark:
            st.markdown(
                f"<div style='background:white;border-radius:10px;padding:.8rem 1rem;text-align:center;height:100%'>"
                f"<div style='font-size:10px;color:#888;margin-bottom:4px'>6 meses</div>"
                f"{spark}"
                f"</div>", unsafe_allow_html=True)

        with col_btn:
            if st.button("⚡ Raio X", key=f"rx_{lid}", use_container_width=True):
                st.session_state.rx_loja_id = lid
                st.rerun()

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

st.divider()
st.download_button("⬇️ Exportar CSV",
    data=df_risco[["conta_id","nome_loja","segmento","gmv_media_2m",
                   "gmv_projetado","var_projetado_pct","gmv_em_risco"]].to_csv(index=False).encode("utf-8"),
    file_name=f"top_sellers_risco_{date.today().strftime('%Y%m%d')}.csv",
    mime="text/csv")
