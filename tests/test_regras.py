"""Regras puras: progressão, pontuação, retomada e validação sem servidor."""
import copy
import unittest
from collections import Counter

from perguntas import NIVEIS, PERGUNTAS
from regras import ErroQuiz, obter_jogo, responder_pergunta


def respostas_ate(total, certas=True):
    return [{"pergunta": p["id"], "escolha": p["correta"] if certas else
             ("b" if p["correta"] == "a" else "a")} for p in PERGUNTAS[:total]]


class RegrasTests(unittest.TestCase):
    def test_catalogo(self):
        self.assertEqual(len(PERGUNTAS), 30)
        self.assertEqual([p["id"] for p in PERGUNTAS], [f"p{i:02d}" for i in range(1, 31)])
        self.assertEqual(Counter(p["nivel"] for p in PERGUNTAS), {1: 10, 2: 10, 3: 10})
        self.assertEqual([n["numero"] for n in NIVEIS], [1, 2, 3])
        for p in PERGUNTAS:
            self.assertEqual(set(p["opcoes"]), {"a", "b"})
            self.assertIn(p["correta"], p["opcoes"])
            for campo in ("titulo", "contexto", "enunciado", "explicacao", "conceito", "fonte"):
                self.assertIsInstance(p[campo], str)
                self.assertTrue(p[campo].strip())
            self.assertRegex(p["fonte"], r"^https://(docs\.python\.org|docs\.docker\.com|developer\.mozilla\.org)/")

    def test_inicio_e_pergunta_publica(self):
        jogo = obter_jogo({"respostas": []})
        self.assertEqual((jogo["respondidas"], jogo["acertos"], jogo["total"], jogo["por_nivel"]), (0, 0, 30, 10))
        self.assertFalse(jogo["concluido"])
        self.assertIsNone(jogo["ultima"])
        for i in range(30):
            p = obter_jogo({"respostas": respostas_ate(i)})["pergunta"]
            self.assertEqual(set(p), {"id", "nivel", "titulo", "contexto", "enunciado", "opcoes", "conceito"})
            self.assertEqual([o["id"] for o in p["opcoes"]], ["a", "b"])
            for o in p["opcoes"]:
                self.assertEqual(set(o), {"id", "texto"})

    def test_trinta_certas_e_trinta_erradas(self):
        for certas in (True, False):
            respostas = []
            for p in PERGUNTAS:
                escolha = p["correta"] if certas else ("b" if p["correta"] == "a" else "a")
                jogo = responder_pergunta({"respostas": respostas, "pergunta": p["id"], "escolha": escolha})
                respostas = jogo["respostas"]
                self.assertEqual(jogo["ultima"]["acertou"], certas)
                self.assertEqual(jogo["ultima"]["explicacao"], p["explicacao"])
                self.assertEqual(jogo["ultima"]["correta"], p["correta"])
                self.assertEqual(jogo["ultima"]["fonte"], p["fonte"])
            self.assertEqual(jogo["acertos"], 30 if certas else 0)
            self.assertEqual(jogo["respondidas"], 30)
            self.assertTrue(jogo["concluido"])
            self.assertIsNone(jogo["pergunta"])
            self.assertIsNone(jogo["ultima"]["proximo_nivel"])
            self.assertTrue(jogo["ultima"]["nivel_concluido"])

    def test_transicoes_independem_de_acertos(self):
        for quantidade, nivel in [(9, 1), (10, 2), (11, 2), (19, 2), (20, 3), (21, 3)]:
            jogo = obter_jogo({"respostas": respostas_ate(quantidade, False)})
            self.assertEqual(jogo["pergunta"]["nivel"], nivel)
            self.assertEqual(jogo["acertos"], 0)
            self.assertEqual(jogo["ultima"]["nivel_concluido"], quantidade in (10, 20))
            proximo = jogo["ultima"]["proximo_nivel"]
            self.assertEqual(proximo, NIVEIS[nivel - 1] if quantidade in (10, 20) else None)
            self.assertEqual(sum(n["respondidas"] for n in jogo["resumo"]), quantidade)

    def test_retomada_recalcula_e_repeticao_nao_duplica(self):
        payload = {"respostas": respostas_ate(10), "pergunta": "p11", "escolha": "a", "acertos": 999}
        original = copy.deepcopy(payload)
        self.assertEqual(responder_pergunta(payload), responder_pergunta(payload))
        self.assertEqual(payload, original)
        self.assertEqual(obter_jogo(payload)["acertos"], 10)
        self.assertEqual(obter_jogo({"respostas": responder_pergunta(payload)["respostas"]}), responder_pergunta(payload))

    def test_respostas_malformadas(self):
        invalidos = [None, [], True, "x", {}, {"respostas": None}, {"respostas": {}},
                     {"respostas": respostas_ate(30) + respostas_ate(1)}]
        invalidos += [{"respostas": [r]} for r in [None, [], True, {},
            {"pergunta": "p02", "escolha": "a"}, {"pergunta": [], "escolha": "a"},
            {"pergunta": "p01", "escolha": "a", "acertos": 1}]]
        invalidos += [{"respostas": [{"pergunta": "p01", "escolha": e}]} for e in [None, [], {}, True, 1, "A", "c", ""]]
        invalidos += [{"respostas": respostas_ate(1) * 2}]
        for payload in invalidos:
            for funcao in (obter_jogo, responder_pergunta):
                with self.subTest(payload=payload, funcao=funcao.__name__), self.assertRaises(ErroQuiz) as erro:
                    funcao(payload)
                self.assertEqual(erro.exception.status, 422)

    def test_responder_exige_pergunta_atual_e_escolha(self):
        for pergunta in [None, [], {}, True, "p02", "p00", ""]:
            with self.assertRaises(ErroQuiz):
                responder_pergunta({"respostas": [], "pergunta": pergunta, "escolha": "a"})
        for escolha in [None, [], {}, True, "A", "c", ""]:
            with self.assertRaises(ErroQuiz):
                responder_pergunta({"respostas": [], "pergunta": "p01", "escolha": escolha})
        with self.assertRaises(ErroQuiz):
            responder_pergunta({"respostas": respostas_ate(30), "pergunta": "p30", "escolha": "a"})
