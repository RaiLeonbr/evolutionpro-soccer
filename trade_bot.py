# tradebot_jarvas_v4.py
import streamlit as st
from datetime import datetime
import re

st.set_page_config(page_title="TradeBot Jarvas Pro v4 — Chat", page_icon="💬", layout="centered")

st.markdown("""
<h2 style='text-align:center;'>💬 TradeBot Jarvas Pro — Chat Edition v4</h2>
<p style='text-align:center;'>Fluxo passo-a-passo: informe times, odds (casa/empate/visitante), placar, tempo, volume e resumo.</p>
""", unsafe_allow_html=True)

# ------------------ Estado da conversa ------------------
if "etapa" not in st.session_state:
    st.session_state.etapa = 0
if "dados" not in st.session_state:
    st.session_state.dados = {}

# Perguntas em sequência (estilo whatsapp)
perguntas = [
    "👋 Olá! Vamos começar — qual o time da casa?",
    "🏟️ Qual o time visitante?",
    "📊 Informe a odd do TIME DA CASA (ex: 1.45):",
    "📊 Informe a odd do TIME VISITANTE (ex: 4.20):",
    "📊 Informe a odd do EMPATE (ex: 3.40):",
    "⚽ Qual o placar atual? (ex: 2 x 1)",
    "⏱️ Quantos minutos de jogo (apenas número)?",
    "💰 Qual o volume do mercado (em R$)? (ex: 3.107.510)",
    "🧠 Faça um breve resumo da partida (quem domina, estilo e sinais táticos):",
]

# Pergunta inicial
if "pergunta" not in st.session_state:
    st.session_state.pergunta = perguntas[0]

# Avança com a resposta do usuário
def avancar_mensagem(resposta):
    etapa = st.session_state.etapa
    dados = st.session_state.dados

    # salva a resposta conforme a etapa
    if etapa == 0:
        dados["time_casa"] = resposta.strip()
    elif etapa == 1:
        dados["time_visitante"] = resposta.strip()
    elif etapa == 2:
        dados["odd_casa"] = resposta.strip()
    elif etapa == 3:
        dados["odd_visitante"] = resposta.strip()
    elif etapa == 4:
        dados["odd_empate"] = resposta.strip()
    elif etapa == 5:
        dados["placar"] = resposta.strip()
    elif etapa == 6:
        dados["minutos"] = resposta.strip()
    elif etapa == 7:
        dados["volume"] = resposta.strip()
    elif etapa == 8:
        dados["resumo"] = resposta.strip()

    # incrementa etapa e define próxima pergunta
    st.session_state.etapa = etapa + 1
    if st.session_state.etapa < len(perguntas):
        st.session_state.pergunta = perguntas[st.session_state.etapa]
    else:
        st.session_state.pergunta = "✅ Dados coletados — gerando análise..."

# Exibe o bot (mensagem inicial / pergunta atual)
with st.chat_message("assistant"):
    etapa = st.session_state.etapa
    if etapa < len(perguntas):
        st.markdown(st.session_state.pergunta)
    else:
        st.markdown("Estou analisando os dados... aguarde um instante. ✅")

# Entrada do usuário (estilo chat)
if prompt := st.chat_input("Digite sua resposta aqui..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    avancar_mensagem(prompt)
    st.rerun()

# Quando todas as etapas forem preenchidas, gerar a análise
if st.session_state.etapa >= len(perguntas):
    d = st.session_state.dados

    # Função utilitária de conversão
    def to_float(x):
        try:
            return float(x.replace(",", ".").replace(" ", ""))
        except:
            return None

    def to_volume(x):
        try:
            return float(re.sub(r"[^\d,\.]", "", x).replace(".", "").replace(",", "."))
        except:
            return None

    # Extrair e converter
    time_casa = d.get("time_casa", "Casa")
    time_visit = d.get("time_visitante", "Visitante")
    odd_casa = to_float(d.get("odd_casa", "")) 
    odd_visit = to_float(d.get("odd_visitante", ""))
    odd_empate = to_float(d.get("odd_empate", ""))
    minutos = None
    try:
        minutos = int(re.findall(r"\d+", d.get("minutos", "0"))[0])
    except:
        minutos = None
    placar_texto = d.get("placar", "")
    resumo_texto = d.get("resumo", "")
    volume_val = to_volume(d.get("volume", ""))

    # Probabilidades implícitas
    probs = {}
    for label, odd in [("Casa", odd_casa), ("Empate", odd_empate), ("Visitante", odd_visit)]:
        if odd and odd > 0:
            probs[label] = 1.0 / odd
        else:
            probs[label] = None

    # Overround / Normalização (calcula probabilidades justas)
    inv_sum = sum([v for v in probs.values() if v is not None])
    normalized = {}
    if inv_sum and inv_sum > 0:
        for k, v in probs.items():
            normalized[k] = (v / inv_sum) if v is not None else None
    else:
        normalized = {k: None for k in probs.keys()}

    # Identifica favorito (menor odd)
    odds_map = { "Casa": odd_casa, "Empate": odd_empate, "Visitante": odd_visit }
    valid_odds = {k:v for k,v in odds_map.items() if v is not None and v>0}
    favorito = None
    if valid_odds:
        favorito = min(valid_odds, key=lambda k: valid_odds[k])  # key name

    # Stake por prob implícita do favorito (se existir)
    stake = 35  # default
    if favorito and probs.get(favorito):
        prob_fav = probs[favorito]
        if prob_fav >= 0.60:
            stake = 40
        elif prob_fav <= 0.45:
            stake = 20
        else:
            stake = 35

    # Classificação do volume
    if volume_val is None:
        liquidez = "🔍 Volume não informado"
    else:
        if volume_val < 200000:
            liquidez = "💀 Mercado fino — pouca liquidez"
        elif 200000 <= volume_val < 800000:
            liquidez = "⚖️ Mercado médio — correções possíveis"
        elif 800000 <= volume_val < 1500000:
            liquidez = "💪 Mercado forte — correções exigem sinal de jogo"
        else:
            liquidez = "🧱 Mercado pesado — apenas eventos mudam as odds"

    # Regras de estratégia (base)
    estrategia = "🔎 Não foi possível definir estratégia clara."
    rationale = []

    # tenta extrair gols
    gols = re.findall(r"\d+", placar_texto)
    gols = [int(g) for g in gols] if gols else []
    casa_gols = gols[0] if len(gols) >= 1 else None
    visit_gols = gols[1] if len(gols) >= 2 else None

    resumo_low = resumo_texto.lower()

    # Heurísticas para decidir Back / Lay
    if favorito and probs.get(favorito) is not None:
        # Se favorito é casa ou visitante
        # cenário: favorito liderando e dominando => back
        if favorito == "Casa" and casa_gols is not None and casa_gols > (visit_gols or 0):
            if "domin" in resumo_low or "pression" in resumo_low or odd_casa <= 1.6:
                estrategia = f"💚 Back no {time_casa} (favorito e está vencendo/pressionando)."
                rationale.append("Favorito vencendo e domínio tático/odd baixa.")
            elif "recuad" in resumo_low or "fech" in resumo_low or "recuado" in resumo_low:
                estrategia = f"💥 Lay no {time_casa} (está vencendo, mas recuado — risco de correção)."
                rationale.append("Favorito recuado — probabilidade de correção aumenta.")
            else:
                estrategia = f"🔎 Aguardar padrão — {time_casa} lidera mas sem leitura clara."
        elif favorito == "Visitante" and visit_gols is not None and visit_gols > (casa_gols or 0):
            if "domin" in resumo_low or "pression" in resumo_low or odd_visit <= 1.6:
                estrategia = f"💚 Back no {time_visit} (favorito e está vencendo/pressionando)."
                rationale.append("Favorito visitante vencendo e dominando.")
            elif "recuad" in resumo_low or "fech" in resumo_low or "recuado" in resumo_low:
                estrategia = f"💥 Lay no {time_visit} (favorito recuado — risco de correção)."
                rationale.append("Favorito recuado — cuidado.")
            else:
                estrategia = f"🔎 Aguardar padrão — {time_visit} lidera mas sem leitura clara."
        else:
            # favorito existe mas não necessariamente vencendo
            # se favorito está perdendo ou sob pressão -> Lay no favorito
            if ((favorito == "Casa" and casa_gols is not None and casa_gols < (visit_gols or 0)) or
                (favorito == "Visitante" and visit_gols is not None and visit_gols < (casa_gols or 0))):
                estrategia = f"💣 Lay no favorito ({'Casa' if favorito=='Casa' else 'Visitante'}) — favorito perdendo."
                rationale.append("Favorito está perdendo — possível correção.")
            else:
                # análise por domínio textual
                if "domin" in resumo_low and favorito == "Casa":
                    estrategia = f"💚 Back no {time_casa} (domínio descrito)."
                elif "domin" in resumo_low and favorito == "Visitante":
                    estrategia = f"💚 Back no {time_visit} (domínio descrito)."
                elif "pression" in resumo_low and favorito:
                    estrategia = f"⚠️ Lay no favorito se houver sinais de pressão do adversário."
                else:
                    estrategia = "🔎 Aguardar padrão claro de jogo antes de entrar."

    else:
        estrategia = "❌ Favorito/odds insuficientes para decisão clara."

    # Recomendações extras (TP / SL)
    tp_pct = 0.30
    sl_pct = 0.50
    if "Back" in estrategia or "Back no" in estrategia:
        # identificar odd alvo e lucro potencial com a odd informada do favorito
        target_odd = odd_casa if "Back no " + time_casa in estrategia or "Casa"==favorito else odd_visit
        if target_odd:
            lucro_pot = (target_odd - 1) * stake
            tp_val = round(lucro_pot * tp_pct, 2)
            sl_val = round(stake * sl_pct, 2)
        else:
            tp_val = None
            sl_val = round(stake * sl_pct, 2)
    elif "Lay" in estrategia or "Lay no" in estrategia or "Lay" in estrategia:
        # responsabilidade = (odd - 1) * stake
        lay_odd = odd_casa if favorito == "Casa" else odd_visit
        if lay_odd:
            responsabilidade = (lay_odd - 1) * stake
            tp_val = round(stake * tp_pct, 2)
            sl_val = round(responsabilidade / 2, 2)  # SL = metade da responsabilidade
        else:
            tp_val = None
            sl_val = None
    else:
        tp_val = None
        sl_val = None

    # Resultado final formatado
    hora = datetime.now().strftime("%H:%M:%S")

    # Monta saída
    st.markdown("---")
    st.markdown(f"### ✅ Análise — {time_casa} x {time_visit}")
    st.markdown(f"- ⏱️ Tempo: **{minutos if minutos is not None else 'N/D'} min**")
    st.markdown(f"- ⚽ Placar: **{placar_texto or 'N/D'}**")
    st.markdown(f"- 📊 Odds informadas: Casa {odd_casa or '-'} — Empate {odd_empate or '-'} — Visitante {odd_visit or '-'}")
    st.markdown(f"- 🔢 Prob. implícitas: Casa {round(probs['Casa']*100,1) if probs['Casa'] else '-'}% • Empate {round(probs['Empate']*100,1) if probs['Empate'] else '-'}% • Visitante {round(probs['Visitante']*100,1) if probs['Visitante'] else '-'}%")
    st.markdown(f"- ⚖️ Prob. normalizadas (fair market): Casa {round(normalized['Casa']*100,1) if normalized['Casa'] else '-'}% • Empate {round(normalized['Empate']*100,1) if normalized['Empate'] else '-'}% • Visitante {round(normalized['Visitante']*100,1) if normalized['Visitante'] else '-'}%")
    st.markdown(f"- 💰 Liquidez: {liquidez}")
    st.markdown(f"- 🧾 Resumo tático: {resumo_texto or '-'}")
    st.markdown("---")

    st.markdown(f"### 🎯 Estratégia sugerida:\n**{estrategia}**")
    if rationale:
        st.markdown("**Racional:** " + " • ".join(rationale))
    st.markdown(f"- 🪙 Stake sugerida: **R$ {stake}**")
    if tp_val is not None:
        st.markdown(f"- 🎯 TP sugerido (estimado): R$ {tp_val}")
    if sl_val is not None:
        st.markdown(f"- ⛔ SL sugerido (estimado): R$ {sl_val}")
    st.markdown(f"_Atualizado às {hora}_")
    st.markdown("---")

    # Oferece reiniciar conversa
    if st.button("✅ Nova análise"):
        st.session_state.etapa = 0
        st.session_state.dados = {}
        st.session_state.pergunta = perguntas[0]
        st.rerun()

    # opcional: salvar em CSV (próxima versão) — placeholder
    st.info("Observação: caso queira, na próxima versão eu já salvo cada análise em CSV (histórico) automaticamente.")

