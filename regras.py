"""Regras puras do quiz: o cliente guarda respostas; Python confere tudo de novo."""
from perguntas import NIVEIS, PERGUNTAS

POR_NIVEL = 10


class ErroQuiz(Exception):
    """Erro esperado, com mensagem legível e status para o servidor HTTP."""

    def __init__(self, mensagem, status=422):
        super().__init__(mensagem)
        self.status = status


def pergunta_publica(pergunta):
    """Só mostra o enunciado e as opções; o gabarito espera a resposta."""
    publica = {chave: pergunta[chave] for chave in
               ("id", "nivel", "titulo", "contexto", "enunciado", "conceito")}
    publica["opcoes"] = [{"id": chave, "texto": pergunta["opcoes"][chave]}
                         for chave in ("a", "b")]
    return publica


def validar_respostas(payload):
    """Aceita somente um prefixo ordenado do catálogo, sem saltos ou duplicatas."""
    if not isinstance(payload, dict):
        raise ErroQuiz("Envie um objeto JSON com a lista respostas.")
    respostas = payload.get("respostas")
    if not isinstance(respostas, list) or len(respostas) > len(PERGUNTAS):
        raise ErroQuiz("Envie uma lista com até 30 respostas.")
    validadas = []
    for indice, resposta in enumerate(respostas):
        if not isinstance(resposta, dict) or set(resposta) != {"pergunta", "escolha"}:
            raise ErroQuiz("Cada resposta precisa conter somente pergunta e escolha.")
        if resposta["pergunta"] != PERGUNTAS[indice]["id"]:
            raise ErroQuiz("Responda às perguntas na ordem, sem pular ou repetir.")
        if not isinstance(resposta["escolha"], str) or resposta["escolha"] not in ("a", "b"):
            raise ErroQuiz("A escolha precisa ser a ou b.")
        validadas.append(dict(resposta))
    return validadas


def montar_estado(respostas):
    """Recalcula pontos com o gabarito do servidor, nunca com pontos do cliente."""
    respondidas = len(respostas)
    resumo = [{"numero": nivel["numero"], "nome": nivel["nome"],
               "respondidas": 0, "acertos": 0} for nivel in NIVEIS]
    for indice, resposta in enumerate(respostas):
        pergunta = PERGUNTAS[indice]
        linha = resumo[pergunta["nivel"] - 1]
        linha["respondidas"] += 1
        linha["acertos"] += int(resposta["escolha"] == pergunta["correta"])
    ultima = None
    if respostas:
        pergunta = PERGUNTAS[respondidas - 1]
        nivel_concluido = respondidas % POR_NIVEL == 0
        proximo_nivel = (dict(NIVEIS[pergunta["nivel"]])
                         if nivel_concluido and respondidas < len(PERGUNTAS) else None)
        ultima = {
            "pergunta": pergunta_publica(pergunta),
            "escolha": respostas[-1]["escolha"], "correta": pergunta["correta"],
            "acertou": respostas[-1]["escolha"] == pergunta["correta"],
            "explicacao": pergunta["explicacao"], "conceito": pergunta["conceito"],
            "fonte": pergunta["fonte"], "nivel_concluido": nivel_concluido,
            "proximo_nivel": proximo_nivel,
        }
    return {
        "versao": 1, "respostas": respostas, "respondidas": respondidas,
        "acertos": sum(linha["acertos"] for linha in resumo),
        "total": len(PERGUNTAS), "por_nivel": POR_NIVEL,
        "niveis": [dict(nivel) for nivel in NIVEIS],
        "concluido": respondidas == len(PERGUNTAS),
        "pergunta": pergunta_publica(PERGUNTAS[respondidas]) if respondidas < len(PERGUNTAS) else None,
        "ultima": ultima, "resumo": resumo,
    }


def obter_jogo(payload):
    """Abre ou retoma a partida sem guardar uma sessão no servidor."""
    return montar_estado(validar_respostas(payload))


def responder_pergunta(payload):
    """Avança uma pergunta mesmo quando a resposta está errada."""
    respostas = validar_respostas(payload)
    if len(respostas) == len(PERGUNTAS):
        raise ErroQuiz("A missão já terminou. Comece uma nova partida para jogar de novo.")
    pergunta = PERGUNTAS[len(respostas)]
    if payload.get("pergunta") != pergunta["id"]:
        raise ErroQuiz("Essa não é a pergunta atual. Retome a partida antes de responder.")
    escolha = payload.get("escolha")
    if not isinstance(escolha, str) or escolha not in ("a", "b"):
        raise ErroQuiz("A escolha precisa ser a ou b.")
    respostas.append({"pergunta": pergunta["id"], "escolha": escolha})
    return montar_estado(respostas)
