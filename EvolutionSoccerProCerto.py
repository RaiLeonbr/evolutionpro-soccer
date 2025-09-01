import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

# ── Funções auxiliares ──
def carregar_jogos(nome_arquivo):
    if not os.path.exists(nome_arquivo):
        st.error(f"Arquivo '{nome_arquivo}' não encontrado.")
        st.stop()
    df = pd.read_excel(nome_arquivo)
    esperadas = {'data', 'rodada', 'mandante', 'visitante', 'gols_mandante', 'gols_visitante'}
    if not esperadas.issubset(set(df.columns)):
        st.error("Arquivo de jogos está com colunas incorretas.")
        st.stop()
    df['data'] = pd.to_datetime(df['data'])
    return df

def carregar_classificacao(nome_arquivo):
    if not os.path.exists(nome_arquivo):
        st.error(f"Arquivo '{nome_arquivo}' não encontrado.")
        st.stop()
    return pd.read_csv(nome_arquivo)

def calcular_aproveitamento(pontos, jogos):
    return (pontos / (jogos * 3)) * 100 if jogos > 0 else 0

def calcular_saldo(df, time):
    gols_pro = df[df['mandante'] == time]['gols_mandante'].sum() + df[df['visitante'] == time]['gols_visitante'].sum()
    gols_contra = df[df['mandante'] == time]['gols_visitante'].sum() + df[df['visitante'] == time]['gols_mandante'].sum()
    return gols_pro - gols_contra

def registrar_usuario(nome, senha):
    if os.path.exists("usuarios_registrados.xlsx"):
        df = pd.read_excel("usuarios_registrados.xlsx")
    else:
        df = pd.DataFrame(columns=["usuario", "senha"])
    if nome in df['usuario'].values:
        return False
    novo_usuario = pd.DataFrame({"usuario": [nome], "senha": [senha]})
    df = pd.concat([df, novo_usuario], ignore_index=True)
    df.to_excel("usuarios_registrados.xlsx", index=False)
    return True

def autenticar_usuario(nome, senha):
    if not os.path.exists("usuarios_registrados.xlsx"):
        return False
    df = pd.read_excel("usuarios_registrados.xlsx")
    return ((df['usuario'] == nome) & (df['senha'] == senha)).any()

def filtrar_jogos(df, time=None, ultimos=True, n=5):
    df_ordenado = df.sort_values('data', ascending=not ultimos)
    if time:
        df_time = df_ordenado[(df_ordenado['mandante'] == time) | (df_ordenado['visitante'] == time)]
    else:
        df_time = df_ordenado
    return df_time.head(n)

# ── Configuração da Página ──
st.set_page_config(page_title="Sistema de Análise", layout="wide")
st.title("Sistema de Análise de Jogos do Brasileirão Série A")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    menu = st.sidebar.radio("Menu", ["Login", "Registrar"])

    if menu == "Login":
        nome = st.sidebar.text_input("Nome")
        senha = st.sidebar.text_input("Senha", type="password")
        if st.sidebar.button("Entrar"):
            if autenticar_usuario(nome, senha):
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.sidebar.error("Nome ou senha incorretos")

    elif menu == "Registrar":
        novo_nome = st.sidebar.text_input("Novo nome")
        nova_senha = st.sidebar.text_input("Nova senha", type="password")
        if st.sidebar.button("Registrar"):
            if registrar_usuario(novo_nome, nova_senha):
                st.sidebar.success("Usuário registrado com sucesso")
            else:
                st.sidebar.error("Usuário já existe")

# ── ÁREA RESTRITA ──
if st.session_state.autenticado:

    df_jogos = carregar_jogos("jogos_atualizados_certo.xlsx")
    df_class = carregar_classificacao("tabela_classificacao_atualizada.csv")
    times = ["Todos"] + sorted(
    [t for t in pd.unique(df_jogos[['mandante', 'visitante']].values.ravel('K')) if pd.notna(t)]
)

    rodadas = sorted(df_jogos['rodada'].unique())
    rodada_selecionada = st.multiselect("Selecione as rodadas", rodadas, default=rodadas)

    col_a, col_b = st.columns(2)
    with col_a:
        time1 = st.selectbox("Selecione o 1º time para análise", times, key="time1")
    with col_b:
        time2 = st.selectbox("Selecione o 2º time para comparação", times, key="time2")

    if rodada_selecionada:
        df_filtrado = df_jogos[df_jogos['rodada'].isin(rodada_selecionada)]

        def analisar_time(df, time):
            df_time = df[(df['mandante'] == time) | (df['visitante'] == time)].copy()
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
                go.Bar(name='Vitórias', x=["Resultados"], y=[vitorias], marker_color='#25c863'),
                go.Bar(name='Empates', x=["Resultados"], y=[empates], marker_color='#f4a261'),
                go.Bar(name='Derrotas', x=["Resultados"], y=[derrotas], marker_color='#e63946')
            ])
            fig_bar.update_layout(barmode='group', title=f"Resultados do {time}", template="plotly_white")
            st.plotly_chart(fig_bar, use_container_width=True)

            df_time = df_time.sort_values("rodada")
            df_time['tendencia'] = df_time['resultado'].map({'V': 1, 'E': 0, 'D': -1}).cumsum()
            fig_linha = px.line(df_time, x="rodada", y="tendencia", markers=True, title=f"Evolução da Performance - {time}")
            st.plotly_chart(fig_linha, use_container_width=True)

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

        st.subheader("Classificação Atual")
        if time1 != "Todos" or time2 != "Todos":
            times_filtrados = [t for t in [time1, time2] if t != "Todos"]
            st.dataframe(df_class[df_class['Equipevde'].isin(times_filtrados)])
        else:
            st.dataframe(df_class)

        st.subheader("Tabela de Jogos Selecionados")
        st.dataframe(df_filtrado[['data', 'rodada', 'mandante', 'gols_mandante', 'gols_visitante', 'visitante']])
    else:
        st.warning("Por favor, selecione ao menos uma rodada para visualizar os dados.")

    # Filtro de últimos e próximos jogos
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

    # Últimas rodadas com resultados
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
    rodada_selecionada = st.selectbox("Selecione uma rodada com resultados disponíveis:", ultimas_5_rodadas)
    jogos_rodada = jogos_com_resultado[jogos_com_resultado['rodada'] == rodada_selecionada]
    st.write(f"Jogos da rodada {rodada_selecionada} com resultado:")
    st.dataframe(jogos_rodada)