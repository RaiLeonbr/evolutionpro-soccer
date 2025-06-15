import streamlit as st
import pandas as pd
import plotly.express as px
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

# ── Configuração da Página ──
st.set_page_config(page_title="Sistema de Análise", layout="wide")
st.title("Sistema de Análise de Jogos do Brasileirão Série A")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

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

if st.session_state.autenticado:
    df_jogos = carregar_jogos("jogos_atualizados_certo.xlsx")
    df_class = carregar_classificacao("tabela_classificacao_atualizada.csv")

    rodadas = sorted(df_jogos['rodada'].unique())
    rodada_selecionada = st.multiselect("Selecione as rodadas", rodadas, default=rodadas)

    times = ["Todos"] + sorted(pd.unique(df_jogos[['mandante', 'visitante']].values.ravel('K')))
    time = st.selectbox("Selecione o time para análise", times)

    if rodada_selecionada:
        df_filtrado = df_jogos[df_jogos['rodada'].isin(rodada_selecionada)]

        if time != "Todos":
            df_filtrado = df_filtrado[(df_filtrado['mandante'] == time) | (df_filtrado['visitante'] == time)]

        st.subheader("Tabela de Jogos")
        st.dataframe(df_filtrado[['data', 'rodada', 'mandante', 'gols_mandante', 'gols_visitante', 'visitante']])

        if time != "Todos":
            df_time = df_filtrado.copy()

            df_time['resultado'] = df_time.apply(
                lambda row: 'V' if (row['mandante'] == time and row['gols_mandante'] > row['gols_visitante']) or
                                    (row['visitante'] == time and row['gols_visitante'] > row['gols_mandante'])
                            else ('E' if row['gols_mandante'] == row['gols_visitante'] else 'D'),
                axis=1
            )

            vitorias = df_time[df_time['resultado'] == 'V'].shape[0]
            empates = df_time[df_time['resultado'] == 'E'].shape[0]
            derrotas = df_time[df_time['resultado'] == 'D'].shape[0]
            jogos = df_time.shape[0]
            pontos = vitorias * 3 + empates
            aproveitamento = calcular_aproveitamento(pontos, jogos)
            saldo = calcular_saldo(df_time, time)

            st.subheader(f"Desempenho do {time}")
            st.markdown(f"""
            - **Jogos:** {jogos}  
            - **Vitórias:** {vitorias}  
            - **Empates:** {empates}  
            - **Derrotas:** {derrotas}  
            - **Pontos:** {pontos}  
            - **Aproveitamento:** {aproveitamento:.2f}%  
            - **Saldo de Gols:** {saldo}  
            """)

            st.subheader("Evolução da Performance por Rodada")
            df_time = df_time.sort_values("rodada")
            df_time['variacao'] = df_time['resultado'].map({'V': 1, 'E': 0, 'D': -1})
            df_time['tendencia'] = df_time['variacao'].cumsum()

            fig = px.line(
                df_time,
                x="rodada",
                y="tendencia",
                markers=True,
                title=f"Evolução da Performance - {time}"
            )

            fig.update_layout(
                xaxis_title="Rodada",
                yaxis_title="Tendência de Resultado",
                yaxis=dict(tickmode='array', tickvals=list(range(df_time['tendencia'].min(), df_time['tendencia'].max() + 1))),
                template="plotly_white"
            )

            st.plotly_chart(fig, use_container_width=True)

            st.markdown(f"## Desempenho Resumido do {time}")
            col1, col2, col3 = st.columns(3)

            def card_desempenho(titulo, valor, cor="#1e1e1e"):
                st.markdown(f"""
                    <div style="
                        background-color: {cor};
                        padding: 1rem;
                        border-radius: 12px;
                        color: white;
                        text-align: center;
                        box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
                        margin-bottom: 10px;
                    ">
                        <h5 style="margin-bottom: 0.5rem;">{titulo}</h5>
                        <h2 style="margin: 0;">{valor}</h2>
                    </div>
                """, unsafe_allow_html=True)

            with col1:
                card_desempenho("Jogos", jogos)
                card_desempenho("Vitórias", vitorias, cor="#25c863")

            with col2:
                card_desempenho("Empates", empates, cor="#f4a261")
                card_desempenho("Derrotas", derrotas, cor="#e63946")

            with col3:
                card_desempenho("Pontos", pontos)
                card_desempenho("Aproveitamento", f"{aproveitamento:.2f}%")
                card_desempenho("Saldo de Gols", saldo)

        st.subheader("Classificação Atual")
        st.dataframe(df_class)
    else:
        st.warning("Por favor, selecione ao menos uma rodada para visualizar os dados.")
