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
    FROM lojaintegrada.pedido_tb_pedido_venda A
    INNER JOIN lojaintegrada.pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id = D.pedido_venda_situacao_id
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
    FROM lojaintegrada.pedido_tb_pedido_venda A
    INNER JOIN lojaintegrada.pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id = D.pedido_venda_situacao_id
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
        FROM lojaintegrada.pedido_tb_pedido_venda A
        INNER JOIN lojaintegrada.pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id=D.pedido_venda_situacao_id
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
        FROM lojaintegrada.pedido_tb_pedido_venda A
        INNER JOIN lojaintegrada.pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id=D.pedido_venda_situacao_id
        INNER JOIN lojaintegrada.pedido_tb_pedido_venda_pagamento E ON A.pedido_venda_id=E.pedido_venda_id
        INNER JOIN lojaintegrada.configuracao_tb_pagamento F ON E.pagamento_id=F.pagamento_id
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
        FROM lojaintegrada.pedido_tb_pedido_venda A
        INNER JOIN lojaintegrada.cliente_tb_cliente B ON A.cliente_id=B.cliente_id
        INNER JOIN lojaintegrada.pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id=D.pedido_venda_situacao_id
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
        FROM lojaintegrada.cliente_tb_cliente B
        INNER JOIN lojaintegrada.pedido_tb_pedido_venda A ON B.cliente_id=A.cliente_id
        INNER JOIN lojaintegrada.pedido_tb_pedido_venda_situacao D ON A.pedido_venda_situacao_id=D.pedido_venda_situacao_id
        WHERE A.conta_id={conta_id}
          AND D.pedido_venda_situacao_nome != 'Pedido Cancelado'
          AND B.cliente_id IN (
            SELECT DISTINCT A2.cliente_id FROM lojaintegrada.pedido_tb_pedido_venda A2
            INNER JOIN lojaintegrada.pedido_tb_pedido_venda_situacao D2 ON A2.pedido_venda_situacao_id=D2.pedido_venda_situacao_id
            WHERE A2.conta_id={conta_id}
              AND CONVERT_TZ(A2.pedido_venda_data_criacao,'+00:00','America/Sao_Paulo')
                  BETWEEN '{ref_ini}' AND '{ref_fim}'
              AND D2.pedido_venda_situacao_nome != 'Pedido Cancelado'
          )
          AND B.cliente_id NOT IN (
            SELECT DISTINCT A3.cliente_id FROM lojaintegrada.pedido_tb_pedido_venda A3
            INNER JOIN lojaintegrada.pedido_tb_pedido_venda_situacao D3 ON A3.pedido_venda_situacao_id=D3.pedido_venda_situacao_id
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

    # Detecta renovação iminente
    data_ini_plano = str(loja.get("data_ini_plano_atual",""))
    dias_renovacao = None
    renovacao_critica = False
    if data_ini_plano and data_ini_plano not in ("None","nan","NaT",""):
        try:
            from dateutil.relativedelta import relativedelta
            dt_ini = datetime.strptime(data_ini_plano[:10], "%Y-%m-%d").date()
            # Ciclo mensal — próxima renovação
            hoje = date.today()
            prox_renovacao = dt_ini.replace(day=dt_ini.day)
            while prox_renovacao <= hoje:
                prox_renovacao = prox_renovacao + relativedelta(months=1)
            dias_renovacao = (prox_renovacao - hoje).days
            if dias_renovacao <= 7 and score >= 50:
                renovacao_critica = True
                score = min(score + 10, 100)
        except Exception:
            pass

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
            + (f"<span style='background:#FEF2F2;color:#991B1B;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700'>⚠️ Renova em {dias_renovacao}d</span>" if renovacao_critica else "")
            + f"</div>",
            unsafe_allow_html=True)
    with col_sc:
        st.markdown(
            f"<div style='text-align:right'>"
            f"<div style='font-size:40px;font-weight:800;color:{cor_score}'>{score}</div>"
            f"<div style='font-size:11px;color:#888'>score de risco</div>"
            f"</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── ALERTA RENOVAÇÃO ──────────────────────────────────────────────────────
    if renovacao_critica:
        st.markdown(
            f"<div style='background:#FEF2F2;border-left:4px solid #E24B4A;border-radius:8px;"
            f"padding:.8rem 1rem;margin-bottom:.8rem'>"
            f"<div style='font-size:13px;font-weight:700;color:#991B1B'>"
            f"⚠️ Renovação em {dias_renovacao} dia(s) — loja em queda</div>"
            f"<div style='font-size:12px;color:#666;margin-top:3px'>"
            f"Plano {status_plano} renova em breve com GMV em queda de {abs(var_gmv or 0)*100:.0f}%. "
            f"Risco alto de cancelamento — CS deve acionar antes da renovação.</div>"
            f"</div>", unsafe_allow_html=True)

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

    # ── SAÚDE DA LOJA — linguagem humana ──────────────────────────────────────
    st.markdown("#### 📊 Saúde da loja")
    tem_prod = str(loja.get("data_primeira_config_produto","")) not in ("","None","nan","NaT")
    tem_pag  = str(loja.get("data_primeira_config_pagamento","")) not in ("","None","nan","NaT")
    tem_log  = str(loja.get("data_primeira_config_logistica","")) not in ("","None","nan","NaT")
    visitas  = safe_int(loja.get("qtde_visitas_ultimos_30d"))
    pedidos  = safe_int(loja.get("qtd_pedido_ultimos_30d"))
    tem_venda= str(loja.get("data_primeira_venda","")) not in ("","None","nan","NaT")

    # Configuração
    cfg_ok = tem_prod and tem_pag and tem_log
    if cfg_ok:
        cfg_emoji, cfg_titulo, cfg_msg, cfg_cor, cfg_bg = "✅", "Loja configurada", "Produto, pagamento e frete ativos", "#166534", "#F0FDF4"
    elif not tem_prod:
        cfg_emoji, cfg_titulo, cfg_msg, cfg_cor, cfg_bg = "🔴", "Sem produto cadastrado", "Nenhum produto ativo — loja não pode vender", "#991B1B", "#FEF2F2"
    elif not tem_pag:
        cfg_emoji, cfg_titulo, cfg_msg, cfg_cor, cfg_bg = "🔴", "Sem pagamento ativo", "Checkout travado — cliente não consegue finalizar compra", "#991B1B", "#FEF2F2"
    else:
        cfg_emoji, cfg_titulo, cfg_msg, cfg_cor, cfg_bg = "🟡", "Sem frete configurado", "Entrega não disponível — pode estar perdendo vendas", "#92400E", "#FFFBEB"

    # Tráfego — taxa de conversão (visitas → pedidos)
    taxa_conv = round(pedidos / visitas * 100, 2) if visitas > 0 else 0
    if visitas == 0:
        traf_emoji, traf_titulo, traf_msg, traf_cor, traf_bg = "🔴", "Loja invisível", "Zero visitas este mês — não está sendo encontrada", "#991B1B", "#FEF2F2"
    elif pedidos == 0:
        traf_emoji, traf_titulo, traf_msg, traf_cor, traf_bg = "🔴", f"Visitantes não compram", f"{visitas:,} visitas e nenhuma venda — problema de conversão", "#991B1B", "#FEF2F2"
    elif taxa_conv >= 1.0:
        traf_emoji, traf_titulo, traf_msg, traf_cor, traf_bg = "✅", f"{taxa_conv:.1f}% de conversão", f"{pedidos:,} vendas em {visitas:,} visitas", "#166534", "#F0FDF4"
    elif taxa_conv >= 0.3:
        traf_emoji, traf_titulo, traf_msg, traf_cor, traf_bg = "🟡", f"{taxa_conv:.1f}% de conversão", f"{pedidos:,} vendas em {visitas:,} visitas — abaixo do esperado", "#92400E", "#FFFBEB"
    else:
        traf_emoji, traf_titulo, traf_msg, traf_cor, traf_bg = "🔴", f"{taxa_conv:.2f}% de conversão", f"{pedidos:,} vendas em {visitas:,} visitas — taxa crítica", "#991B1B", "#FEF2F2"

    # Conversão
    if pedidos >= 50:
        conv_emoji, conv_titulo, conv_msg, conv_cor, conv_bg = "✅", f"{pedidos} pedidos/mês", "Vendendo bem", "#166534", "#F0FDF4"
    elif pedidos > 0:
        conv_emoji, conv_titulo, conv_msg, conv_cor, conv_bg = "🟡", f"{pedidos} pedidos/mês", "Vendendo pouco para o tráfego que tem", "#92400E", "#FFFBEB"
    elif tem_venda:
        conv_emoji, conv_titulo, conv_msg, conv_cor, conv_bg = "🔴", "Sem vendas recentes", "Loja que vendia parou de vender", "#991B1B", "#FEF2F2"
    else:
        conv_emoji, conv_titulo, conv_msg, conv_cor, conv_bg = "🔴", "Nunca vendeu", "Loja configurada mas sem nenhuma venda", "#991B1B", "#FEF2F2"

    # Retenção — baseada na tendência semanal
    if var_gmv is None:
        ret_emoji, ret_titulo, ret_msg, ret_cor, ret_bg = "⚪", "Sem histórico", "Dados insuficientes para calcular tendência", "#888", "#F5F2EE"
    elif var_gmv >= 0.05:
        ret_emoji, ret_titulo, ret_msg, ret_cor, ret_bg = "✅", f"GMV +{var_gmv*100:.1f}%", "Crescendo — tendência positiva", "#166534", "#F0FDF4"
    elif var_gmv >= -0.10:
        ret_emoji, ret_titulo, ret_msg, ret_cor, ret_bg = "🟡", f"GMV {var_gmv*100:+.1f}%", "Estável — monitorar nos próximos dias", "#92400E", "#FFFBEB"
    elif var_gmv >= -0.30:
        ret_emoji, ret_titulo, ret_msg, ret_cor, ret_bg = "🟠", f"GMV {var_gmv*100:+.1f}% — monitorar", "Queda moderada — verificar causa antes de agravar", "#92400E", "#FFFBEB"
    elif var_gmv >= -0.50:
        ret_emoji, ret_titulo, ret_msg, ret_cor, ret_bg = "🔴", f"GMV {var_gmv*100:+.1f}% — atenção", "Queda forte — acionar CS esta semana", "#991B1B", "#FEF2F2"
    else:
        ret_emoji, ret_titulo, ret_msg, ret_cor, ret_bg = "🔴", f"GMV {var_gmv*100:+.1f}% — crítico", "Colapso de faturamento — intervenção urgente", "#991B1B", "#FEF2F2"

    cd = st.columns(4)
    for col, (emoji_c, titulo, msg, cor_c, bg_c) in zip(cd, [
        (cfg_emoji,  cfg_titulo,  cfg_msg,  cfg_cor,  cfg_bg),
        (traf_emoji, traf_titulo, traf_msg, traf_cor, traf_bg),
        (conv_emoji, conv_titulo, conv_msg, conv_cor, conv_bg),
        (ret_emoji,  ret_titulo,  ret_msg,  ret_cor,  ret_bg),
    ]):
        with col:
            st.markdown(
                f"<div style='background:{bg_c};border-radius:12px;padding:1rem;height:100%'>"
                f"<div style='font-size:24px;margin-bottom:.4rem'>{emoji_c}</div>"
                f"<div style='font-size:13px;font-weight:700;color:{cor_c};margin-bottom:.3rem'>{titulo}</div>"
                f"<div style='font-size:12px;color:#555;line-height:1.5'>{msg}</div>"
                f"</div>", unsafe_allow_html=True)

    st.divider()

    # ── TENDÊNCIA SEMANAL ─────────────────────────────────────────────────────
    st.markdown("#### 📉 Tendência de GMV — últimas 2 semanas vs mesmo período 30 dias atrás")
    if tend and tend.get("gmv_anterior"):
        def _fmt_dt(s):
            try:
                from datetime import datetime
                return datetime.strptime(str(s)[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
            except:
                return str(s)[:10]
        st.caption(f"Atual: {_fmt_dt(tend.get('atual_de',''))} → {_fmt_dt(tend.get('atual_ate',''))} | Ref: {_fmt_dt(tend.get('ref_de',''))} → {_fmt_dt(tend.get('ref_ate',''))}")
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

        df_pag["ticket_medio"] = pd.to_numeric(df_pag["ticket_medio"], errors="coerce").fillna(0)
        df_pag["gmv_estimado"]  = df_pag["total_pedidos"] * df_pag["ticket_medio"]

        tab_ped, tab_gmv = st.tabs(["📦 Quantidade de pedidos", "💰 Receita por canal"])

        with tab_ped:
            try:
                piv_ped = df_pag.pivot_table(index="forma_pagamento", columns="mes",
                                             values="total_pedidos", aggfunc="sum", fill_value=0).reset_index()
                piv_ped.columns.name = None
                # Formata como inteiros
                for c in piv_ped.columns[1:]:
                    piv_ped[c] = piv_ped[c].astype(int)
                st.dataframe(piv_ped, use_container_width=True, hide_index=True)
            except Exception:
                st.dataframe(df_pag[["mes","forma_pagamento","total_pedidos"]],
                             use_container_width=True, hide_index=True)

        with tab_gmv:
            try:
                piv_gmv = df_pag.pivot_table(index="forma_pagamento", columns="mes",
                                             values="gmv_estimado", aggfunc="sum", fill_value=0).reset_index()
                piv_gmv.columns.name = None
                # Formata como BRL
                for c in piv_gmv.columns[1:]:
                    piv_gmv[c] = piv_gmv[c].apply(lambda v: fmt_brl(v) if v > 0 else "—")
                st.dataframe(piv_gmv, use_container_width=True, hide_index=True)
                st.caption("GMV estimado = pedidos × ticket médio por forma de pagamento")
            except Exception:
                st.dataframe(df_pag[["mes","forma_pagamento","gmv_estimado"]],
                             use_container_width=True, hide_index=True)
        st.divider()

    # ── NOVOS VS RECORRENTES ──────────────────────────────────────────────────
    if not df_nr.empty:
        st.markdown("#### 👥 Base de clientes")
        df_nr["receita"] = pd.to_numeric(df_nr.get("receita", df_nr["total_pedidos"]), errors="coerce").fillna(0)
        df_nr["total_pedidos"] = pd.to_numeric(df_nr["total_pedidos"], errors="coerce").fillna(0)

        rec  = df_nr[df_nr["tipo_cliente"]=="Recorrente"].sort_values("mes")
        novo = df_nr[df_nr["tipo_cliente"]=="Novo"].sort_values("mes")

        # Pega últimos 2 meses completos (exclui mês atual parcial)
        from datetime import date as _date
        mes_atual = _date.today().strftime("%Y-%m")

        rec_hist  = rec[rec["mes"] != mes_atual]
        novo_hist = novo[novo["mes"] != mes_atual]

        rec_ult  = rec_hist.iloc[-1]  if len(rec_hist)  >= 1 else None
        rec_ant  = rec_hist.iloc[-2]  if len(rec_hist)  >= 2 else None
        novo_ult = novo_hist.iloc[-1] if len(novo_hist) >= 1 else None
        novo_ant = novo_hist.iloc[-2] if len(novo_hist) >= 2 else None

        col_rec, col_nov = st.columns(2)

        with col_rec:
            if rec_ult is not None:
                r1 = safe_float(rec_ult["receita"])
                p1 = safe_int(rec_ult["total_pedidos"])
                mes1 = str(rec_ult["mes"])
                if rec_ant is not None:
                    r0 = safe_float(rec_ant["receita"])
                    p0 = safe_int(rec_ant["total_pedidos"])
                    mes0 = str(rec_ant["mes"])
                    var_r = (r1-r0)/r0*100 if r0 > 0 else 0
                    var_p = (p1-p0)/p0*100 if p0 > 0 else 0
                    cor_r = "#E24B4A" if var_r < -10 else "#F59E0B" if var_r < 0 else "#166534"
                    sinal = "+" if var_r > 0 else ""
                    st.markdown(
                        f"<div style='background:white;border-radius:12px;padding:1rem'>"
                        f"<div style='font-size:12px;color:#888;text-transform:uppercase;margin-bottom:.5rem'>Clientes recorrentes</div>"
                        f"<div style='display:flex;justify-content:space-between;align-items:flex-start'>"
                        f"<div>"
                        f"<div style='font-size:18px;font-weight:700;color:#1A2E2B'>{fmt_brl(r1)}</div>"
                        f"<div style='font-size:12px;color:#888'>{p1} pedidos em {mes1}</div>"
                        f"</div>"
                        f"<div style='text-align:right'>"
                        f"<div style='font-size:20px;font-weight:800;color:{cor_r}'>{sinal}{var_r:.0f}%</div>"
                        f"<div style='font-size:11px;color:#888'>vs {mes0}</div>"
                        f"</div></div>"
                        f"<div style='margin-top:.8rem;font-size:12px;color:{'#991B1B' if var_r <= -20 else '#92400E' if var_r < 0 else '#166534'}'>"
                        + (f"⚠️ Base fidelizada encolhendo — acionar CS antes de agravar" if var_r <= -20
                           else f"📉 Leve queda de recorrentes — monitorar" if var_r < 0
                           else f"✅ Recorrentes estáveis ou crescendo")
                        + f"</div></div>",
                        unsafe_allow_html=True)

        with col_nov:
            if novo_ult is not None:
                n1 = safe_float(novo_ult["receita"])
                q1 = safe_int(novo_ult["total_pedidos"])
                mes1 = str(novo_ult["mes"])
                if novo_ant is not None:
                    n0 = safe_float(novo_ant["receita"])
                    q0 = safe_int(novo_ant["total_pedidos"])
                    mes0 = str(novo_ant["mes"])
                    var_n = (n1-n0)/n0*100 if n0 > 0 else 0
                    cor_n = "#E24B4A" if var_n < -20 else "#F59E0B" if var_n < 0 else "#166534"
                    sinal = "+" if var_n > 0 else ""
                    st.markdown(
                        f"<div style='background:white;border-radius:12px;padding:1rem'>"
                        f"<div style='font-size:12px;color:#888;text-transform:uppercase;margin-bottom:.5rem'>Novos clientes</div>"
                        f"<div style='display:flex;justify-content:space-between;align-items:flex-start'>"
                        f"<div>"
                        f"<div style='font-size:18px;font-weight:700;color:#1A2E2B'>{fmt_brl(n1)}</div>"
                        f"<div style='font-size:12px;color:#888'>{q1} pedidos em {mes1}</div>"
                        f"</div>"
                        f"<div style='text-align:right'>"
                        f"<div style='font-size:20px;font-weight:800;color:{cor_n}'>{sinal}{var_n:.0f}%</div>"
                        f"<div style='font-size:11px;color:#888'>vs {mes0}</div>"
                        f"</div></div>"
                        f"<div style='margin-top:.8rem;font-size:12px;color:{'#991B1B' if var_n <= -30 else '#92400E' if var_n < 0 else '#166534'}'>"
                        + (f"🔴 Aquisição caindo forte — sem reposição de base" if var_n <= -30
                           else f"📉 Menos novos chegando — verificar canais de aquisição" if var_n < 0
                           else f"✅ Aquisição de novos saudável")
                        + f"</div></div>",
                        unsafe_allow_html=True)

        # Diagnóstico consolidado
        if rec_ant is not None and novo_ant is not None:
            r_cai  = (safe_float(rec_ult["receita"])  - safe_float(rec_ant["receita"]))  / max(safe_float(rec_ant["receita"]),1)  * 100
            n_cai  = (safe_float(novo_ult["receita"]) - safe_float(novo_ant["receita"])) / max(safe_float(novo_ant["receita"]),1) * 100
            if r_cai <= -20 and n_cai <= -20:
                diag_base = "🔴 Colapso duplo — recorrentes e novos caindo ao mesmo tempo. Risco alto de encolhimento acelerado da base."
                cor_diag = "#991B1B"; bg_diag = "#FEF2F2"; bd_diag = "#E24B4A"
            elif r_cai <= -20:
                diag_base = "⚠️ A loja está perdendo clientes fiéis mais rápido do que conquista novos. Risco de encolhimento de base nos próximos 60 dias."
                cor_diag = "#92400E"; bg_diag = "#FFFBEB"; bd_diag = "#F59E0B"
            elif n_cai <= -30:
                diag_base = "📉 Recorrentes estáveis mas aquisição caindo. Sem renovação de base no médio prazo."
                cor_diag = "#92400E"; bg_diag = "#FFFBEB"; bd_diag = "#F59E0B"
            elif r_cai > 5 and n_cai > 5:
                diag_base = "✅ Base crescendo em novos e recorrentes. Loja saudável."
                cor_diag = "#166534"; bg_diag = "#F0FDF4"; bd_diag = "#86EFAC"
            else:
                diag_base = None

            if diag_base:
                st.markdown(
                    f"<div style='background:{bg_diag};border-left:4px solid {bd_diag};border-radius:8px;"
                    f"padding:.8rem 1rem;margin-top:.8rem'>"
                    f"<div style='font-size:13px;color:{cor_diag}'>{diag_base}</div>"
                    f"</div>", unsafe_allow_html=True)

        with st.expander("Ver tabela completa", expanded=False):
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
            f"padding:.8rem 1rem;margin-bottom:1rem'>"
            f"<div style='font-size:14px;font-weight:700;color:#991B1B'>"
            f"💰 {fmt_brl(receita_risco)} em receita histórica em risco</div>"
            f"<div style='font-size:12px;color:#666;margin-top:3px'>"
            f"Clientes que compravam regularmente e pararam. Abaixo estão os mais importantes — priorize o contato.</div>"
            f"</div>", unsafe_allow_html=True)

        def _prioridade(receita, ticket, dias_ausente):
            if receita >= 20000 or ticket >= 2000:
                return "🔴 Prioridade 1", "#FEF2F2", "#991B1B", "Cliente VIP — contato direto esta semana (WhatsApp ou telefone)"
            elif receita >= 8000 or ticket >= 500:
                return "🟡 Prioridade 2", "#FFFBEB", "#92400E", "Cliente recorrente de valor — e-mail personalizado ou ligação"
            else:
                return "⚪ Prioridade 3", "#F5F2EE", "#5A7A78", "Cliente regular — incluir em campanha de reativação"

        def _perfil(email, ticket):
            email = str(email or "").lower()
            dominios_corp = [".com.br", ".ind.br", ".org.br", ".gov.br"]
            emails_corp   = ["compras@","financeiro@","suprimentos@","vendas@","comercial@","contato@","sac@"]
            is_corp = any(d in email for d in dominios_corp) or any(e in email for e in emails_corp)
            if is_corp and ticket >= 1000:
                return "🏢 B2B — comprador corporativo. Abordagem comercial direta, mencionar histórico de pedidos."
            elif is_corp:
                return "🏢 B2B — empresa. Contato pelo e-mail corporativo com proposta de reativação."
            elif ticket >= 500:
                return "⭐ Consumidor premium. Oferecer condição especial ou frete grátis."
            else:
                return "👤 Consumidor regular. Incluir em campanha de reativação com desconto."

        for _, row in df_ch.head(10).iterrows():
            nome      = str(row.get("cliente_nome","—"))
            email_c   = str(row.get("cliente_email","—"))
            ped_tot   = safe_int(row.get("total_pedidos",0))
            rec_hist  = safe_float(row.get("receita_historico",0))
            tick      = safe_float(row.get("ticket_medio",0))
            ult_ped   = str(row.get("ultimo_pedido","—"))[:10]

            # Dias ausente
            try:
                from datetime import datetime as _dt2
                dias_aus = (_dt2.today() - _dt2.strptime(ult_ped, "%Y-%m-%d")).days
                dias_str = f"{dias_aus} dias sem comprar"
            except:
                dias_aus = 999
                dias_str = "data desconhecida"

            badge, bg_p, cor_p, acao_p = _prioridade(rec_hist, tick, dias_aus)
            perfil_txt = _perfil(email_c, tick)

            st.markdown(
                f"<div style='background:white;border-radius:12px;padding:1rem 1.2rem;margin-bottom:.6rem;"
                f"border-left:4px solid {'#E24B4A' if 'Prioridade 1' in badge else '#F59E0B' if 'Prioridade 2' in badge else '#C8C0B4'}'>"
                f"<div style='display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:.5rem'>"
                f"<div>"
                f"<div style='font-size:14px;font-weight:700;color:#1A2E2B'>{nome}</div>"
                f"<div style='font-size:12px;color:#888;margin-top:2px'>{email_c}</div>"
                f"</div>"
                f"<span style='background:{bg_p};color:{cor_p};padding:3px 10px;border-radius:20px;"
                f"font-size:11px;font-weight:700;white-space:nowrap'>{badge}</span>"
                f"</div>"
                f"<div style='display:flex;gap:1.5rem;margin-top:.6rem;flex-wrap:wrap'>"
                f"<div><div style='font-size:10px;color:#AAA;text-transform:uppercase'>Pedidos histórico</div>"
                f"<div style='font-size:13px;font-weight:600;color:#1A2E2B'>{ped_tot}</div></div>"
                f"<div><div style='font-size:10px;color:#AAA;text-transform:uppercase'>Receita histórica</div>"
                f"<div style='font-size:13px;font-weight:600;color:#1A2E2B'>{fmt_brl(rec_hist)}</div></div>"
                f"<div><div style='font-size:10px;color:#AAA;text-transform:uppercase'>Ticket médio</div>"
                f"<div style='font-size:13px;font-weight:600;color:#1A2E2B'>{fmt_brl(tick)}</div></div>"
                f"<div><div style='font-size:10px;color:#AAA;text-transform:uppercase'>Último pedido</div>"
                f"<div style='font-size:13px;font-weight:600;color:#E24B4A'>{ult_ped} · {dias_str}</div></div>"
                f"</div>"
                f"<div style='margin-top:.6rem;font-size:12px;color:#555;background:#F8F5F0;"
                f"border-radius:6px;padding:.4rem .8rem'>"
                f"💬 {perfil_txt}<br>→ <strong>{acao_p}</strong>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True)

        if len(df_ch) > 10:
            with st.expander(f"Ver mais {len(df_ch)-10} clientes", expanded=False):
                df_show = df_ch[10:].copy()
                if "receita_historico" in df_show: df_show["receita_historico"] = df_show["receita_historico"].apply(fmt_brl)
                if "ticket_medio"      in df_show: df_show["ticket_medio"]      = df_show["ticket_medio"].apply(fmt_brl)
                st.dataframe(df_show[["cliente_nome","cliente_email","total_pedidos","receita_historico","ticket_medio","ultimo_pedido"]],
                             use_container_width=True, hide_index=True)
        st.divider()

    # ── AÇÃO RECOMENDADA ──────────────────────────────────────────────────────
    st.markdown("#### 🎯 Ação recomendada")
    tab_n2, tab_cs, tab_lider = st.tabs(["🔧 N2 · Automação","📞 CS · Sucesso do Cliente","📊 Liderança"])

    with tab_n2:
        # Monta diagnóstico técnico baseado nos dados reais
        var_g = safe_float(tend.get("var_gmv_pct")) if tend and tend.get("gmv_anterior") else None
        var_p = safe_float(tend.get("var_pedidos_pct")) if tend and tend.get("gmv_anterior") else None
        var_t = safe_float(tend.get("var_ticket_pct")) if tend and tend.get("gmv_anterior") else None
        gmv_risco_val = safe_float(tend.get("gmv_em_risco")) if tend else 0
        n_churned = len(df_ch) if not df_ch.empty else 0

        # Título do diagnóstico
        if var_g is not None and var_g <= -90:
            titulo_n2 = f"🔴 Loja parou de vender completamente ({var_g:+.0f}% GMV)"
            cor_titulo = "#991B1B"; bg_titulo = "#FEF2F2"
        elif var_g is not None and var_g <= -50:
            titulo_n2 = f"🔴 Colapso de faturamento — queda de {abs(var_g):.0f}% no GMV"
            cor_titulo = "#991B1B"; bg_titulo = "#FEF2F2"
        elif var_g is not None and var_g <= -20:
            titulo_n2 = f"🟠 Queda significativa de {abs(var_g):.0f}% no GMV — investigar causa"
            cor_titulo = "#92400E"; bg_titulo = "#FFFBEB"
        elif status_real == "ONBOARDING INCOMPLETO":
            titulo_n2 = "🔴 Gargalo de configuração impedindo vendas"
            cor_titulo = "#991B1B"; bg_titulo = "#FEF2F2"
        elif status_real == "NUNCA VENDEU":
            titulo_n2 = "🟠 Loja configurada mas sem nenhuma conversão"
            cor_titulo = "#92400E"; bg_titulo = "#FFFBEB"
        elif status_real == "SEM VENDAS RECENTES":
            titulo_n2 = "🟡 Loja que vendia entrou em inatividade"
            cor_titulo = "#92400E"; bg_titulo = "#FFFBEB"
        else:
            titulo_n2 = "✅ Loja saudável — monitoramento de rotina"
            cor_titulo = "#166534"; bg_titulo = "#F0FDF4"

        st.markdown(
            f"<div style='background:{bg_titulo};border-radius:10px;padding:.8rem 1rem;margin-bottom:1rem'>"
            f"<div style='font-size:14px;font-weight:700;color:{cor_titulo}'>{titulo_n2}</div>"
            f"</div>", unsafe_allow_html=True)

        # O que os dados mostram
        evidencias = []
        if var_g is not None:
            evidencias.append(f"GMV {var_g:+.1f}% nas últimas 2 semanas vs mesmo período 30 dias atrás")
        if var_p is not None:
            evidencias.append(f"Volume de pedidos {var_p:+.1f}%")
        if var_t is not None:
            evidencias.append(f"Ticket médio {var_t:+.1f}%")
        if gmv_risco_val > 0:
            evidencias.append(f"{fmt_brl(gmv_risco_val)} em GMV abaixo do período de referência")
        if n_churned > 0:
            receita_ch = safe_float(df_ch["receita_historico"].sum()) if "receita_historico" in df_ch.columns else 0
            evidencias.append(f"{n_churned} clientes churned identificados — {fmt_brl(receita_ch)} em receita histórica em risco")

        # Detecta mix de pagamento removido
        pag_removido = None
        if not df_pag.empty and "mes" in df_pag.columns:
            meses_p = sorted(df_pag["mes"].unique())
            if len(meses_p) >= 2:
                f_rec = set(df_pag[df_pag["mes"]==meses_p[-1]]["forma_pagamento"].tolist())
                f_ant = set(df_pag[df_pag["mes"]==meses_p[-2]]["forma_pagamento"].tolist())
                removidas_p = f_ant - f_rec
                if removidas_p:
                    pag_removido = ", ".join(removidas_p)
                    evidencias.append(f"Forma de pagamento removida recentemente: {pag_removido}")

        if evidencias:
            st.markdown("**O que os dados mostram:**")
            for ev in evidencias:
                st.markdown(f"→ {ev}")

        st.markdown("")

        # Checklist de investigação
        checklist = []

        if var_g is not None and var_g <= -90:
            checklist = [
                f"Verificar se a forma de pagamento principal está ativa em Configurações → Pagamentos" + (f" (especialmente: {pag_removido})" if pag_removido else ""),
                "Testar o checkout da loja — consegue iniciar e finalizar um pedido?",
                "Verificar se o domínio está ativo e apontando corretamente",
                "Checar se há erros no painel de integrações de pagamento",
                "Se pagamento ativo, verificar se o estoque dos produtos principais está zerado",
            ]
        elif var_g is not None and var_g <= -50:
            checklist = [
                "Rodar diagnóstico de mix de pagamento — verificar se alguma forma foi removida",
                f"Analisar os {n_churned} clientes churned — identificar padrão de saída (B2B, forma de pgto, segmento)",
                "Verificar variação de cupons ativos — desconto excessivo pode estar comprimindo GMV",
                "Checar se houve mudança de preço ou catálogo no período",
                "Comparar pedidos cancelados deste período vs período anterior",
            ]
        elif var_g is not None and var_g <= -20:
            checklist = [
                "Monitorar por mais 7 dias antes de acionar CS — pode ser variação sazonal",
                "Verificar mix de pagamento — alguma forma perdendo volume?",
                f"Observar recorrentes: {n_churned} clientes sumiram — B2B ou B2C?",
                "Preparar diagnóstico completo se queda persistir na próxima semana",
            ]
        elif status_real == "ONBOARDING INCOMPLETO":
            falta = []
            if not tem_prod: falta.append("cadastrar produto")
            if not tem_pag:  falta.append("ativar pagamento (Pagali)")
            if not tem_log:  falta.append("configurar frete (Enviali)")
            checklist = [
                f"Gargalo identificado: {' + '.join(falta) if falta else 'verificar configurações'}",
                "Acionar automação de e-mail de onboarding com o passo específico que falta",
                "Se loja paga e travada há 7+ dias: escalar para CS com prioridade",
            ]
        elif status_real == "NUNCA VENDEU":
            checklist = [
                f"Verificar taxa de conversão: {visitas:,} visitas e {pedidos} pedidos — problema de produto ou preço?",
                "Checar se o checkout está funcionando (teste manual)",
                "Verificar se os produtos têm foto, descrição e preço competitivo",
                "Acionar e-mail com checklist de primeiras vendas",
            ]
        else:
            checklist = ["Monitoramento de rotina — sem ação técnica necessária agora"]

        st.markdown("**Checklist de investigação:**")
        for i, item in enumerate(checklist, 1):
            st.markdown(
                f"<div style='background:white;border-radius:8px;padding:.6rem .9rem;margin-bottom:4px;"
                f"display:flex;align-items:flex-start;gap:.6rem'>"
                f"<span style='background:#F2EDE4;color:#0D4F4A;font-size:11px;font-weight:700;"
                f"padding:2px 7px;border-radius:20px;white-space:nowrap'>☐ {i}</span>"
                f"<span style='font-size:13px;color:#1A2E2B'>{item}</span>"
                f"</div>",
                unsafe_allow_html=True)

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
        gmv_30d_l    = safe_float(loja.get("vlr_gmv_ultimos_30d"))
        pedidos_30d_l= safe_int(loja.get("qtd_pedido_ultimos_30d"))
        var_gmv_l    = safe_float(tend.get("var_gmv_pct")) if tend and tend.get("gmv_anterior") else None
        gmv_risco_l  = safe_float(tend.get("gmv_em_risco")) if tend else 0
        rec_risco_l  = safe_float(df_ch["receita_historico"].sum()) if not df_ch.empty and "receita_historico" in df_ch.columns else 0
        n_ch_l       = len(df_ch) if not df_ch.empty else 0

        # Situação executiva
        if var_gmv_l is not None and var_gmv_l <= -90:
            sit_titulo = "🔴 Loja parou de vender"
            sit_desc   = f"Loja com {fmt_brl(gmv_30d_l)} de GMV mensal zerou completamente nas últimas 2 semanas."
            sit_causa  = "Causa provável: troca ou remoção de gateway de pagamento."
            sit_acao   = "CS acionar hoje — loja pode retomar em 24h se gateway for reativado."
            sit_cor    = "#991B1B"; sit_bg = "#FEF2F2"; sit_bd = "#E24B4A"
        elif var_gmv_l is not None and var_gmv_l <= -50:
            sit_titulo = "🔴 Colapso de faturamento"
            sit_desc   = f"GMV caiu {abs(var_gmv_l):.0f}% nas últimas 2 semanas. Loja com histórico sólido em queda acelerada."
            sit_causa  = f"{n_ch_l} clientes que compravam regularmente pararam. Possível ruptura comercial ou problema de pagamento."
            sit_acao   = "CS deve acionar os principais clientes esta semana. N2 investigar mix de pagamento."
            sit_cor    = "#991B1B"; sit_bg = "#FEF2F2"; sit_bd = "#E24B4A"
        elif var_gmv_l is not None and var_gmv_l <= -20:
            sit_titulo = "🟠 Declínio acelerado"
            sit_desc   = f"GMV caiu {abs(var_gmv_l):.0f}% vs período de referência. Tendência preocupante mas ainda reversível."
            sit_causa  = f"Base de clientes fiéis encolhendo. {n_ch_l} churned identificados."
            sit_acao   = "Monitorar por 7 dias. Se persistir, acionar CS com diagnóstico completo."
            sit_cor    = "#92400E"; sit_bg = "#FFFBEB"; sit_bd = "#F59E0B"
        elif status_real in ("ONBOARDING INCOMPLETO", "NUNCA VENDEU"):
            sit_titulo = "🟡 Loja travada no onboarding"
            sit_desc   = f"Loja {status_plano} sem vender. Gargalo de configuração impedindo a primeira venda."
            sit_causa  = "Configuração incompleta — sem produto, pagamento ou frete ativo."
            sit_acao   = "CS contatar para destravar. Loja paga travada = MRR em risco."
            sit_cor    = "#92400E"; sit_bg = "#FFFBEB"; sit_bd = "#F59E0B"
        else:
            sit_titulo = "✅ Loja saudável"
            sit_desc   = f"{fmt_brl(gmv_30d_l)} GMV · {pedidos_30d_l} pedidos nos últimos 30 dias."
            sit_causa  = "Sem sinais de risco no momento."
            sit_acao   = "Monitoramento de rotina — sem ação necessária."
            sit_cor    = "#166534"; sit_bg = "#F0FDF4"; sit_bd = "#86EFAC"

        st.markdown(
            f"<div style='background:{sit_bg};border-left:4px solid {sit_bd};border-radius:10px;"
            f"padding:1rem 1.2rem;margin-bottom:1rem'>"
            f"<div style='font-size:16px;font-weight:700;color:{sit_cor};margin-bottom:.5rem'>{sit_titulo}</div>"
            f"<div style='font-size:13px;color:#333;line-height:1.7'>"
            f"{sit_desc}<br>{sit_causa}"
            f"</div>"
            f"<div style='margin-top:.8rem;background:white;border-radius:6px;padding:.6rem .8rem;"
            f"font-size:13px;font-weight:600;color:{sit_cor}'>"
            f"→ {sit_acao}"
            f"</div></div>", unsafe_allow_html=True)

        # Impacto financeiro
        col_imp1, col_imp2, col_imp3 = st.columns(3)
        with col_imp1:
            st.markdown(
                f"<div style='background:white;border-radius:10px;padding:.8rem'>"
                f"<div style='font-size:11px;color:#888;text-transform:uppercase'>GMV últimos 30d</div>"
                f"<div style='font-size:20px;font-weight:700;color:#1A2E2B'>{fmt_brl(gmv_30d_l)}</div>"
                f"<div style='font-size:12px;color:{'#E24B4A' if var_gmv_l and var_gmv_l < 0 else '#1ABCB0'}'>"
                f"{f'{var_gmv_l:+.1f}% semanal' if var_gmv_l is not None else '—'}</div>"
                f"</div>", unsafe_allow_html=True)
        with col_imp2:
            st.markdown(
                f"<div style='background:white;border-radius:10px;padding:.8rem'>"
                f"<div style='font-size:11px;color:#888;text-transform:uppercase'>GMV em risco este mês</div>"
                f"<div style='font-size:20px;font-weight:700;color:#E24B4A'>{fmt_brl(gmv_risco_l)}</div>"
                f"<div style='font-size:12px;color:#888'>vs período de referência</div>"
                f"</div>", unsafe_allow_html=True)
        with col_imp3:
            st.markdown(
                f"<div style='background:white;border-radius:10px;padding:.8rem'>"
                f"<div style='font-size:11px;color:#888;text-transform:uppercase'>Receita histórica em risco</div>"
                f"<div style='font-size:20px;font-weight:700;color:#E24B4A'>{fmt_brl(rec_risco_l)}</div>"
                f"<div style='font-size:12px;color:#888'>{n_ch_l} clientes churned</div>"
                f"</div>", unsafe_allow_html=True)


    st.divider()

    # ── IA — DIAGNÓSTICO NARRATIVO ───────────────────────────────────────────
    st.divider()
    st.markdown("#### 🤖 Diagnóstico com IA")

    def chamar_groq(contexto):
        try:
            import requests
            key = st.secrets.get("groq", {}).get("api_key", "")
            if not key:
                return None, "Groq API key não configurada nos secrets."

            system = """Você é um analista especialista em e-commerce e retenção de lojistas da Loja Integrada.
Analise os dados fornecidos e gere um diagnóstico executivo em português brasileiro.
Seja direto, específico com os números e orientado a ação.
Estruture em 3 partes:
1. O que está acontecendo (2-3 frases)
2. Causas identificadas (bullets)
3. Ações recomendadas por prioridade (bullets)"""

            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "llama3-70b-8192",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": contexto}
                    ],
                    "max_tokens": 800,
                    "temperature": 0.7,
                },
                timeout=30
            )
            resp.raise_for_status()
            texto = resp.json()["choices"][0]["message"]["content"]
            return texto, None
        except Exception as e:
            return None, str(e)

    def montar_contexto_ia(loja, tend, df_ch, df_nr, status_real, var_gmv):
        nome  = loja.get("nome_loja","—")
        seg   = loja.get("segmento_loja","—")
        gmv30 = fmt_brl(loja.get("vlr_gmv_ultimos_30d",0))
        ped30 = safe_int(loja.get("qtd_pedido_ultimos_30d",0))

        linhas = [
            "LOJA: {} | SEGMENTO: {} | STATUS: {}".format(nome, seg, status_real),
            "GMV 30d: {} | Pedidos 30d: {}".format(gmv30, ped30),
        ]

        if tend and tend.get("gmv_anterior"):
            linhas += [
                "",
                "TENDÊNCIA SEMANAL:",
                "- GMV atual: {} ({:+.1f}%)".format(fmt_brl(tend.get("gmv_atual")), safe_float(tend.get("var_gmv_pct"))),
                "- Pedidos: {} ({:+.1f}%)".format(safe_int(tend.get("pedidos_atual")), safe_float(tend.get("var_pedidos_pct"))),
                "- Ticket médio: {} ({:+.1f}%)".format(fmt_brl(tend.get("ticket_atual")), safe_float(tend.get("var_ticket_pct"))),
                "- GMV em risco: {}".format(fmt_brl(tend.get("gmv_em_risco", 0))),
            ]

        if not df_ch.empty and "receita_historico" in df_ch.columns:
            receita_ch = safe_float(df_ch["receita_historico"].sum())
            linhas += ["", "CLIENTES CHURNED: {} identificados | {} em receita histórica".format(len(df_ch), fmt_brl(receita_ch))]
            for _, r in df_ch.head(3).iterrows():
                linhas.append("- {} ({}): {} historico".format(
                    r.get("cliente_nome","—"), r.get("cliente_email","—"), fmt_brl(r.get("receita_historico",0))))

        if not df_nr.empty:
            rec = df_nr[df_nr["tipo_cliente"]=="Recorrente"].sort_values("mes")
            if len(rec) >= 2:
                r0 = safe_float(rec["receita"].iloc[0])
                r1 = safe_float(rec["receita"].iloc[-1])
                if r0 > 0:
                    linhas += ["", "RECORRENTES: de {} para {} ({:+.1f}% no periodo)".format(
                        fmt_brl(r0), fmt_brl(r1), (r1-r0)/r0*100)]

        if not df_pag.empty and "mes" in df_pag.columns:
            meses_p = sorted(df_pag["mes"].unique())
            if len(meses_p) >= 2:
                f_rec = set(df_pag[df_pag["mes"]==meses_p[-1]]["forma_pagamento"].tolist())
                f_ant = set(df_pag[df_pag["mes"]==meses_p[-2]]["forma_pagamento"].tolist())
                removidas = f_ant - f_rec
                if removidas:
                    linhas += ["", "PAGAMENTO REMOVIDO: {}".format(", ".join(removidas))]

        return "\n".join(linhas)

    # Botão de IA
    if "ia_resultado" not in st.session_state:
        st.session_state["ia_resultado"] = None
    if "ia_loja_id" not in st.session_state:
        st.session_state["ia_loja_id"] = None

    col_ia_btn, col_ia_clear = st.columns([3,1])
    with col_ia_btn:
        if st.button("🤖 Gerar diagnóstico com IA", use_container_width=True, key="btn_ia_groq"):
            ctx = montar_contexto_ia(loja, tend, df_ch, df_nr, status_real, var_gmv)
            with st.spinner("Analisando com IA..."):
                resultado, erro = chamar_groq(ctx)
            if erro:
                st.error(f"Erro: {erro}")
            else:
                st.session_state["ia_resultado"] = resultado
                st.session_state["ia_loja_id"]   = lid
    with col_ia_clear:
        if st.button("✕ Limpar", use_container_width=True, key="btn_ia_clear"):
            st.session_state["ia_resultado"] = None

    if st.session_state.get("ia_resultado") and st.session_state.get("ia_loja_id") == lid:
        texto = st.session_state["ia_resultado"]
        st.markdown(
            f"<div style='background:#F8F5F0;border:1px solid #E8E4DE;border-radius:12px;"
            f"padding:1.2rem;font-size:13px;line-height:1.8;color:#1A2E2B;margin-top:.5rem'>"
            f"{texto.replace(chr(10), '<br>')}"
            f"</div>", unsafe_allow_html=True)
        st.caption("Gerado por llama3-70b via Groq · Para produção: migrar para gptoss-120b via LiteLLM proxy da LI")

    # ── ROADMAP ───────────────────────────────────────────────────────────────
    st.markdown("""
    <div style='background:#0D4F4A;border-radius:12px;padding:1rem 1.5rem'>
        <div style='font-size:11px;color:#1ABCB0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px'>
            🗺️ Próximos passos — Roadmap
        </div>
        <div style='display:flex;gap:1rem;flex-wrap:wrap'>
            <div style='flex:1;min-width:180px;background:#1A6A64;border-radius:8px;padding:.8rem'>
                <div style='font-size:13px;font-weight:700;color:#D4F53C;margin-bottom:4px'>🤖 Diagnóstico com IA</div>
                <div style='font-size:12px;color:#9DBDBB;line-height:1.6'>
                    gptoss-120b analisa todos os dados e gera diagnóstico narrativo automático —
                    igual ao estudo manual da Arco Íris LED, mas para qualquer loja em segundos.
                </div>
            </div>
            <div style='flex:1;min-width:180px;background:#1A6A64;border-radius:8px;padding:.8rem'>
                <div style='font-size:13px;font-weight:700;color:#D4F53C;margin-bottom:4px'>✉️ E-mail personalizado</div>
                <div style='font-size:12px;color:#9DBDBB;line-height:1.6'>
                    IA redige e-mail consultivo para o lojista explicando o que detectamos —
                    pronto para o CS disparar, sem escrever nada manualmente.
                </div>
            </div>
            <div style='flex:1;min-width:180px;background:#1A6A64;border-radius:8px;padding:.8rem'>
                <div style='font-size:13px;font-weight:700;color:#D4F53C;margin-bottom:4px'>📤 Integração HubSpot</div>
                <div style='font-size:12px;color:#9DBDBB;line-height:1.6'>
                    Cria tarefa automática para o CS com briefing completo do diagnóstico —
                    sem copiar e colar entre sistemas.
                </div>
            </div>
        </div>
        <div style='font-size:11px;color:#5A9A96;margin-top:8px'>
            Aguardando: LiteLLM proxy acessível externamente + HubSpot API token
        </div>
    </div>
    """, unsafe_allow_html=True)

    if False:  # placeholder — remover quando LiteLLM estiver acessível
        st.markdown("#### 🤖 Diagnóstico com IA + HubSpot")

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
