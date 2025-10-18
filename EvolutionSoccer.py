import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# Pasta base (garante que os arquivos fiquem na mesma pasta do script)
PASTA_BASE = os.path.dirname(__file__)

# ---------- Cache: evita recarregar tudo a cada interação ----------
@st.cache_data
def obter_soup_wikipedia():
    url = "https://pt.wikipedia.org/wiki/Campeonato_Brasileiro_de_Futebol_de_2025_-_S%C3%A9rie_A"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        requisicao = requests.get(url, headers=headers, timeout=10)  # Timeout de 10 segundos
        requisicao.raise_for_status()  # dispara erro se não for 200
        return BeautifulSoup(requisicao.text, "html.parser")
    except requests.exceptions.Timeout:
        st.error("Tempo de resposta esgotado. Tente novamente mais tarde.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao acessar a Wikipedia: {e}")
        return None

@st.cache_data
def extrair_tabela_soup_por_titulo(_soup, titulo):
    for header in _soup.find_all(["h2", "h3"]):
        if titulo.lower() in header.get_text(strip=True).lower():
            tabela = header.find_next("table", {"class": "wikitable"})
            if tabela is not None:
                return pd.read_html(str(tabela))[0]
    return None

# ---------- Funções de IO (cacheadas, mas não chamam st.* internamente) ----------
@st.cache_data
def carregar_jogos_arquivo(caminho_completo):
    if not os.path.exists(caminho_completo):
        raise FileNotFoundError(caminho_completo)
    df = pd.read_excel(caminho_completo)
    df['data'] = pd.to_datetime(df['data'])
    return df

@st.cache_data
def carregar_classificacao_arquivo(caminho_completo, sheet_name="Classificação"):
    if not os.path.exists(caminho_completo):
        raise FileNotFoundError(caminho_completo)
    # tenta ler Excel com aba "Classificação" (se existir)
    try:
        return pd.read_excel(caminho_completo, sheet_name=sheet_name)
    except Exception:
        # se falhar, tenta CSV
        return pd.read_csv(caminho_completo)

# ---------- Funções utilitárias ----------
def calcular_aproveitamento(pontos, jogos):
    return (pontos / (jogos * 3)) * 100 if jogos > 0 else 0

def calcular_saldo(df, time):
    gols_pro = df[df['mandante'] == time]['gols_mandante'].sum() + df[df['visitante'] == time]['gols_visitante'].sum()
    gols_contra = df[df['mandante'] == time]['gols_visitante'].sum() + df[df['visitante'] == time]['gols_mandante'].sum()
    return gols_pro - gols_contra

def registrar_usuario(nome, senha):
    path = os.path.join(PASTA_BASE, "usuarios_registrados.xlsx")
    if os.path.exists(path):
        df = pd.read_excel(path)
    else:
        df = pd.DataFrame(columns=["usuario", "senha"])
    if nome in df['usuario'].values:
        return False
    novo_usuario = pd.DataFrame({"usuario": [nome], "senha": [senha]})
    df = pd.concat([df, novo_usuario], ignore_index=True)
    df.to_excel(path, index=False)
    return True

def autenticar_usuario(nome, senha):
    path = os.path.join(PASTA_BASE, "usuarios_registrados.xlsx")
    if not os.path.exists(path):
        return False
    df = pd.read_excel(path)
    return ((df['usuario'] == nome) & (df['senha'] == senha)).any()


def filtrar_jogos(df, time=None, ultimos=True, n=5):
    df_ordenado = df.sort_values('data', ascending=not ultimos)
    if time:
        df_time = df_ordenado[(df_ordenado['mandante'] == time) | (df_ordenado['visitante'] == time)]
    else:
        df_time = df_ordenado
    return df_time.head(n)

# ---------- Extrai tabelas da Wikipedia e salva arquivo de classificação (uma vez por execução do código) ----------
def atualizar_tabelas_wikipedia(e_salvar=True):
    soup = obter_soup_wikipedia()
    tabela_classificacao = extrair_tabela_soup_por_titulo(soup, "Classificação")
    tabela_jogos = extrair_tabela_soup_por_titulo(soup, "Confrontos")

    if e_salvar and tabela_classificacao is not None:
        caminho_xlsx = os.path.join(PASTA_BASE, "tabela_classificacao_atualizada.xlsx")
        # Salva em uma planilha com duas abas (Classificação e Confrontos) quando possível
        with pd.ExcelWriter(caminho_xlsx) as writer:
            tabela_classificacao.to_excel(writer, sheet_name="Classificação", index=False)
            if tabela_jogos is not None:
                tabela_jogos.to_excel(writer, sheet_name="Confrontos", index=False)
        return caminho_xlsx, tabela_classificacao, tabela_jogos
    return None, tabela_classificacao, tabela_jogos

# ---------- Autenticação ----------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    menu = st.sidebar.radio("Menu", ["Login", "Registrar"], key="menu_login")
    if menu == "Login":
        nome = st.sidebar.text_input("Nome")
        senha = st.sidebar.text_input("Senha", type="password")
        if st.sidebar.button("Entrar"):
            if autenticar_usuario(nome, senha):
                st.session_state.autenticado = True
                st.rerun()  # rerun após login
            else:
                st.sidebar.error("Nome ou senha incorretos")
    else:  # Registrar
        novo_nome = st.sidebar.text_input("Novo nome")
        nova_senha = st.sidebar.text_input("Nova senha", type="password")
        if st.sidebar.button("Registrar"):
            if registrar_usuario(novo_nome, nova_senha):
                st.sidebar.success("Usuário registrado com sucesso")
            else:
                st.sidebar.error("Usuário já existe")
else:
    # ---------- Atualização de tabelas APÓS login ----------
    try:
        arquivo_classificacao_xlsx, tabela_classificacao, tabela_jogos = atualizar_tabelas_wikipedia(e_salvar=True)
        if arquivo_classificacao_xlsx:
            st.sidebar.success("Classificação atualizada (fonte: Wikipedia).")
    except Exception as e:
        st.sidebar.error(f"Erro ao atualizar dados da Wikipedia: {e}")
        tabela_classificacao, tabela_jogos = None, None
        arquivo_classificacao_xlsx = None

# ---------- Configuração da página ----------
st.set_page_config(page_title="Sistema de Análise", layout="wide")
st.title("Sistema de Análise de Jogos do Brasileirão Série A")

# Atualiza as tabelas (opcional: você pode comentar essa chamada se não quiser atualizar sempre)
try:
    arquivo_classificacao_xlsx, tabela_classificacao, tabela_jogos = atualizar_tabelas_wikipedia(e_salvar=True)
    # se quiser, exiba um log
    if arquivo_classificacao_xlsx:
        st.sidebar.success("Classificação atualizada (fonte: Wikipedia).")
except Exception as e:
    st.sidebar.error(f"Erro ao atualizar dados da Wikipedia: {e}")
    tabela_classificacao, tabela_jogos = None, None
    arquivo_classificacao_xlsx = None

# ---------- Autenticação ----------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    menu = st.sidebar.radio("Menu", ["Login", "Registrar"])
    if menu == "Login":
        nome = st.sidebar.text_input("Nome", key="login_nome")
        senha = st.sidebar.text_input("Senha", type="password", key="login_senha")
        if st.sidebar.button("Entrar",key="botao_entrar"):
            if autenticar_usuario(nome, senha):
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.sidebar.error("Nome ou senha incorretos")
    else:  # Registrar
        novo_nome = st.sidebar.text_input("Novo nome")
        nova_senha = st.sidebar.text_input("Nova senha", type="password")
        if st.sidebar.button("Registrar"):
            if registrar_usuario(novo_nome, nova_senha):
                st.sidebar.success("Usuário registrado com sucesso")
            else:
                st.sidebar.error("Usuário já existe")

# ---------- ÁREA RESTRITA (tudo que usa df_jogos/df_class deve ficar aqui) ----------
if st.session_state.autenticado:
    # Carrega arquivos locais (tratando exceções)
    try:
        caminho_jogos = os.path.join(PASTA_BASE, "jogos_atualizados.xlsx")
        df_jogos = carregar_jogos_arquivo(caminho_jogos)
    except FileNotFoundError:
        st.error(f"Arquivo de jogos não encontrado: {caminho_jogos}")
        st.stop()

    # Para classificação, tentamos usar o xlsx gerado pela wiki; se não existir, tenta CSV do projeto
    caminho_classificacao_xlsx = os.path.join(PASTA_BASE, "tabela_classificacao_atualizada.xlsx")
    caminho_classificacao_csv = os.path.join(PASTA_BASE, "tabela_classificacao_atualizada.csv")
    caminho_para_abrir = None
    if os.path.exists(caminho_classificacao_xlsx):
        caminho_para_abrir = caminho_classificacao_xlsx
    elif os.path.exists(caminho_classificacao_csv):
        caminho_para_abrir = caminho_classificacao_csv
    else:
        st.warning("Arquivo de classificação atualizado não encontrado. A parte de classificação ficará vazia.")
        df_class = pd.DataFrame()  # tabela vazia
    if caminho_para_abrir:
        try:
            df_class = carregar_classificacao_arquivo(caminho_para_abrir, sheet_name="Classificação")
        except Exception as e:
            st.error(f"Erro ao carregar classificação: {e}")
            st.stop()

    # Lista de times
    times = ["Todos"] + sorted(
        [t for t in pd.unique(df_jogos[['mandante', 'visitante']].values.ravel('K')) if pd.notna(t)]
    )

    # Rodadas e seletor (default = rodada atual)
    rodadas = sorted(df_jogos['rodada'].unique())
    rodada_atual = max(rodadas) if len(rodadas) else 1

    rodada_selecionada = st.multiselect(
        "Selecione as rodadas",
        rodadas,
        default=[rodada_atual]
    )

    col_a, col_b = st.columns(2)
    with col_a:
        time1 = st.selectbox("Selecione o 1º time para análise", times, key="time1")
    with col_b:
        time2 = st.selectbox("Selecione o 2º time para comparação", times, key="time2")

    if rodada_selecionada:
        df_filtrado = df_jogos[df_jogos['rodada'].isin(rodada_selecionada)]

        # Função analisar_time definida aqui (antes de ser usada pelo botão)
        def analisar_time(df, time):
            df_time = df[(df['mandante'] == time) | (df['visitante'] == time)].copy()
            if df_time.empty:
                st.info(f"Não há jogos para {time} nas rodadas selecionadas.")
                return

            df_time['resultado'] = df_time.apply(
                lambda row: 'V' if (row['mandante'] == time and row['gols_mandante'] > row['gols_visitante']) or
                            (row['visitante'] == time and row['gols_visitante'] > row['gols_mandante'])
                            else ('E' if row['gols_mandante'] == row['gols_visitante'] else 'D'),
                axis=1
            )
            vitorias = (df_time['resultado'] == 'V').sum()
            empates = (df_time['resultado'] == 'E').sum()
            derrotas = (df_time['resultado'] == 'D').sum()
            jogos = len(df_time)
            pontos = vitorias * 3 + empates
            aproveitamento = calcular_aproveitamento(pontos, jogos)
            saldo = calcular_saldo(df_time, time)

            gols_feitos = df_time[df_time['mandante'] == time]['gols_mandante'].sum() + df_time[df_time['visitante'] == time]['gols_visitante'].sum()
            gols_mandante = df_time[df_time['mandante'] == time]['gols_mandante'].sum()
            gols_visitante = df_time[df_time['visitante'] == time]['gols_visitante'].sum()
            gols_sofridos_visitante = df_time[df_time['visitante'] == time]['gols_mandante'].sum()
            media_mandante = gols_mandante / max(1, len(df_time[df_time['mandante'] == time]))
            media_visitante = gols_visitante / max(1, len(df_time[df_time['visitante'] == time]))

            st.markdown(f"## Desempenho do {time}")
            st.markdown(f"""
            - **Jogos:** {jogos}  
            - **Vitórias:** {vitorias}  
            - **Empates:** {empates}  
            - **Derrotas:** {derrotas}  
            - **Pontos:** {pontos}  
            - **Aproveitamento:** {aproveitamento:.2f}%  
            - **Saldo de Gols:** {saldo}  
            - **Gols Feitos (Total):** {gols_feitos}  
            - **Gols Mandante:** {gols_mandante}  
            - **Gols Visitante:** {gols_visitante}  
            - **Gols Sofridos como Visitante:** {gols_sofridos_visitante}  
            - **Média Gols Mandante:** {media_mandante:.2f}  
            - **Média Gols Visitante:** {media_visitante:.2f}  
            """)

            fig_bar = go.Figure(data=[
                go.Bar(name='Vitórias', x=["Resultados"], y=[vitorias]),
                go.Bar(name='Empates', x=["Resultados"], y=[empates]),
                go.Bar(name='Derrotas', x=["Resultados"], y=[derrotas])
            ])
            fig_bar.update_layout(barmode='group', title=f"Resultados do {time}", template="plotly_white")
            st.plotly_chart(fig_bar, use_container_width=True)

            df_time = df_time.sort_values("rodada")
            df_time['tendencia'] = df_time['resultado'].map({'V': 1, 'E': 0, 'D': -1}).cumsum()
            fig_linha = px.line(df_time, x="rodada", y="tendencia", markers=True, title=f"Evolução da Performance - {time}")
            st.plotly_chart(fig_linha, use_container_width=True)

        # Botão: sorteia quando gerar as análises (lazy loading)
        if st.button("🔍 Gerar análises detalhadas"):
            if time1 != "Todos" and time2 != "Todos" and time1 != time2:
                col1, col2 = st.columns(2)
                with col1:
                    analisar_time(df_filtrado, time1)
                with col2:
                    analisar_time(df_filtrado, time2)
            elif time1 != "Todos":
                analisar_time(df_filtrado, time1)
            elif time2 != "Todos":
                analisar_time(df_filtrado, time2)
        else:
            st.info("Selecione os times e clique em 'Gerar análises detalhadas' para carregar gráficos.")

        # Exibição da classificação (limpa e protegida contra ausência de df_class)
        st.subheader("Classificação Atual")
        if not df_class.empty and (time1 != "Todos" or time2 != "Todos"):
            times_filtrados = [t for t in [time1, time2] if t != "Todos"]
            st.dataframe(df_class[df_class.iloc[:,0].isin(times_filtrados)].head(50))  # ajusta coluna índice dinamicamente
        elif not df_class.empty:
            st.dataframe(df_class.head(50))
        else:
            st.info("Classificação não disponível.")

        st.subheader("Tabela de Jogos Selecionados")
        st.dataframe(df_filtrado[['data', 'rodada', 'mandante', 'gols_mandante', 'gols_visitante', 'visitante']].head(100))
    else:
        st.warning("Por favor, selecione ao menos uma rodada para visualizar os dados.")

    # ---------- Filtro de últimos e próximos jogos ----------
    st.subheader("📅 Filtro de Jogos por Rodada")
    times_disponiveis = sorted(
        [t for t in pd.unique(df_jogos[['mandante', 'visitante']].values.ravel('K')) if pd.notna(t)]
    )

    time_filtro = st.selectbox("Selecione um time para análise dos jogos", ["Todos"] + times_disponiveis)
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Mostrar Últimos 5 Jogos"):
            df_filtro = filtrar_jogos(df_jogos, None if time_filtro == "Todos" else time_filtro, ultimos=True, n=5)
            st.dataframe(df_filtro[['data', 'rodada', 'mandante', 'gols_mandante', 'gols_visitante', 'visitante']])

    with col2:
        if st.button("Mostrar Próximos 5 Jogos"):
            df_futuros = df_jogos[df_jogos['gols_mandante'].isna() | df_jogos['gols_visitante'].isna()]
            df_filtro = filtrar_jogos(df_futuros, None if time_filtro == "Todos" else time_filtro, ultimos=False, n=5)
            st.dataframe(df_filtro[['data', 'rodada', 'mandante', 'visitante']])

    # ---------- Últimas rodadas com resultados ----------
    jogos_com_resultado = df_jogos[
        df_jogos['gols_mandante'].notnull() &
        df_jogos['gols_visitante'].notnull() &
        (df_jogos['gols_mandante'] != '') &
        (df_jogos['gols_visitante'] != '')
    ]

    rodadas_completas = jogos_com_resultado.groupby('rodada').filter(
        lambda x: x.shape[0] == df_jogos[df_jogos['rodada'] == x['rodada'].iloc[0]].shape[0]
    )['rodada'].unique()

    ultimas_5_rodadas = sorted(rodadas_completas)[-5:]
    if len(ultimas_5_rodadas) > 0:
        rodada_resultados = st.selectbox("Selecione uma rodada com resultados disponíveis:", ultimas_5_rodadas)
        jogos_rodada = jogos_com_resultado[jogos_com_resultado['rodada'] == rodada_resultados]
        st.write(f"Jogos da rodada {rodada_resultados} com resultado:")
        st.dataframe(jogos_rodada)
    else:
        st.info("Ainda não há rodadas completas com resultados.")
