# Orbit Dispatch

Um quiz de Python e Docker numa central espacial que também sofre com reunião demais, deploy de última hora e café de menos.

Uma pergunta curta, dois botões grandes e uma nave que reage ao clique. Acertou? Ganhou um ponto. Errou? A tela mostra a resposta certa. O “Por quê?” abre a explicação completa quando você quiser. A cada dez respostas, uma nova órbita é liberada com uma animação. A missão é estudar sem transformar o jogo numa aula.

## O jogo

São **30 perguntas, em três níveis de 10**:

1. **Base de lançamento:** variáveis, tipos, listas, dicionários, condições e funções em Python.
2. **Em órbita:** mais Python, JSON e os pedidos HTTP que ligam navegador e servidor.
3. **Controle da missão:** imagens, containers, portas, logs, volumes, rede e diagnóstico no Docker.

Cada pergunta tem duas alternativas e uma resposta correta. Cada acerto vale um ponto. Depois de **10 perguntas respondidas**, você passa ao próximo nível, mesmo que tenha errado algumas. O jogo termina na pergunta 30; não existe um quarto nível escondido nem uma fase repetida anunciada como nova.

Uma resposta por pergunta. A correção fica em “Por quê?”, sem bloquear a próxima pergunta. O progresso fica salvo neste navegador, e o Python confere tudo de novo ao recarregar a página. Em uma janela privada, ele pode desaparecer quando a janela for fechada. Se o armazenamento for bloqueado, a tela avisa.

## Colocar a central no ar

Com o Docker Desktop aberto, entre na pasta do projeto:

```sh
cd /Users/mauro/Documents/Dev/orbit-dispatch
docker compose up -d --build
```

Abra **http://localhost:8001**.

O primeiro comando pode levar um pouco mais de tempo para baixar a imagem-base. `-d` deixa o serviço rodando sem prender seu terminal. Para conferir:

```sh
docker compose ps
docker compose logs -f
```

`Ctrl+C` encerra o acompanhamento dos logs, não o servidor que está em segundo plano.

## O que acontece quando você responde

1. `static/app.js` envia um `POST /api/responder` com o identificador da pergunta, sua escolha e as respostas anteriores.
2. `server.py` recebe o JSON e chama `responder_pergunta()`, em `regras.py`.
3. O Python valida a ordem, confere o gabarito de `perguntas.py`, recalcula o placar e monta a explicação.
4. O navegador mostra o resultado e salva as escolhas no `localStorage`, o armazenamento local do navegador.

Exemplo de pedido na primeira pergunta:

```json
{
  "respostas": [],
  "pergunta": "p01",
  "escolha": "a"
}
```

A ideia central da correção cabe nesta comparação:

```python
acertou = escolha == pergunta["correta"]
```

`==` compara valores. O resultado é `True` quando a escolha coincide com o gabarito. A soma dos acertos vira o placar. Não há IA gerando uma correção na hora: perguntas, gabaritos e explicações são um banco editorial que você pode ler e modificar.

Abra **“O código por trás”** no jogo para acompanhar trechos reais da troca. As respostas certas das próximas perguntas não são enviadas antes da correção.

Ao recarregar, `POST /api/jogo` envia o histórico salvo para o servidor conferir. O navegador não manda um placar para o Python simplesmente aceitar. Isso é um exercício de validação, **não um sistema antifraude**: quem controla o navegador pode editar suas próprias respostas. Não há contas, ranking ou disputa online.

## Mapa do projeto

| Arquivo | O que estudar |
| --- | --- |
| `perguntas.py` | Listas e dicionários com as 30 perguntas e três níveis. Cada pergunta tem uma fonte oficial. |
| `regras.py` | Validação, comparação, contagem de acertos e avanço de nível. Não depende de HTTP. |
| `server.py` | Rotas HTTP, JSON, arquivos estáticos e encerramento do servidor. |
| `static/app.js` | `fetch()`, eventos, atualização da tela e `localStorage`. |
| `static/index.html` e `static/styles.css` | Estrutura, estilos, foco e estados das respostas. |
| `Dockerfile` | A receita para construir a imagem Python do projeto. |
| `compose.yaml` | Porta local, processo, restrições do container e verificação de saúde. |
| `tests/` | Testes de conteúdo, regras, HTTP e estrutura da interface. |

## Primeiro exercício: mudar uma explicação

1. Abra `perguntas.py` e encontre `p01`.
2. Reescreva o campo `explicacao`. Preserve a correção técnica; a resenha pode ser sua.
3. Salve e observe que a aplicação no Docker ainda usa a cópia antiga.
4. Rode:

```sh
docker compose up -d --build
```

Recarregue a página. Use **“Recomeçar”** e confirme para voltar à primeira pergunta com zero pontos. Responda e confira seu texto.

O Dockerfile usa `COPY`: o código entra na imagem durante a construção. Salvar no editor não muda uma imagem pronta. `--build` reconstrói a imagem; o Compose recria o container quando necessário. O progresso fica no navegador, não na imagem.

## Segundo exercício: entender o nível

Em `regras.py`, procure `POR_NIVEL = 10` e o uso de `%`. O resto da divisão ajuda a identificar o fim de cada bloco de dez respostas.

Rode os testes e veja as fronteiras **9 → 10 → 11**, **19 → 20 → 21** e o encerramento na pergunta 30. Dez respostas certas rendem dez pontos. Dez respostas erradas rendem zero pontos, mas também concluem o nível: o erro faz parte do exercício.

Para adicionar conteúdo depois, acrescente um nível completo no banco, com dez perguntas, IDs únicos, gabaritos, explicações e fontes. Atualize os testes e os textos que anunciam a quantidade. A interface lê os níveis e totais recebidos do Python; o catálogo publicado aqui contém exatamente três níveis.

## Terceiro exercício: encerrar de verdade

O botão **“Encerrar servidor”**, dentro de “O código por trás”, pede confirmação antes de chamar `POST /api/parar`. Essa rota encerra o servidor Python. Como ele é o processo principal da aplicação no container, o container para também.

A página continua aberta, mas não consegue corrigir novas respostas. Confirme no terminal:

```sh
docker compose ps -a
```

Para voltar:

```sh
docker compose up -d
```

Depois, recarregue a página. O progresso salvo no navegador é revalidado pelo servidor. A configuração usa `restart: "no"` justamente para que a central não volte sozinha neste exercício.

Também é possível parar pelo terminal com `docker compose stop`. Nenhum desses comandos limpa o progresso do navegador.

## Testes

No container, com Python 3.13:

```sh
docker compose run --rm --no-deps app python -m unittest discover -s tests -v
```

Ou com Python 3.13 ou superior instalado:

```sh
python3 -m unittest discover -s tests -v
```

Os testes HTTP usam um servidor separado, numa porta temporária. Eles não encerram o jogo que você deixou aberto.

## Sem Docker, para comparar

Não há dependências Python externas:

```sh
python3 server.py
```

Abra http://localhost:8001. Se o container já estiver usando essa porta, escolha outra para o teste:

```sh
python3 server.py --port 8002
```

Nesse caso, abra http://localhost:8002. São origens diferentes, então o navegador guarda um progresso separado para cada porta. Ao editar o Python nessa execução direta, reinicie o processo para carregar a alteração.

## Se não abrir

- Confira se o Docker Desktop está rodando.
- Na pasta do projeto, rode `docker compose up -d --build`.
- Use `docker compose ps` e `docker compose logs --tail 40` para ver o estado e os registros.
- Acesse `localhost:8001`, não a porta interna 8000. O mapeamento é `127.0.0.1:8001:8000`.
- Se o servidor foi reconstruído enquanto a página estava aberta, recarregue para renovar o token de envio.
- Se o progresso salvo estiver inválido, a tela informa o problema sem apagá-lo automaticamente. “Recomeçar” inicia uma nova rodada após confirmação.

## Limites deste laboratório

A aplicação fica acessível apenas no próprio computador. Usa validação de entrada, token de envio, verificação de origem e host, arquivos estáticos permitidos e container sem privilégios extras. Essas medidas não transformam o projeto num serviço pronto para publicação.

Não há banco de dados nem dados pessoais. As escolhas ficam na chave `orbit-dispatch-quiz-v1` do `localStorage`; recomeçar altera só essa chave. Servidor e container não guardam partidas.

O arquivo `project.json` registra nome, porta, entrada `/` e saúde `/api/saude` para facilitar um futuro site reunindo os sete projetos. Antes de uma publicação pública, será preciso rever hospedagem, HTTPS, acesso, proteção da rota de encerramento e persistência. Nada é publicado automaticamente.

## Referências

A simplicidade e o humor cotidiano vêm da proposta do [Mesa 8000](https://github.com/mauro-mota/estudo-docker), sem repetir seu tema. Os conceitos do quiz têm referências na própria correção:

- [Tutorial de Python](https://docs.python.org/3/tutorial/)
- [Docker: primeiros passos](https://docs.docker.com/get-started/)
- [HTTP na MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP)

A resposta imediata ao clique e a progressão visível também têm como referência o [Cookie Clicker](https://orteil.dashnet.org/cookieclicker/). As ilustrações vetoriais da nave, dos planetas e do satélite são originais deste projeto. Não há assets copiados do jogo. Animações respeitam a preferência de movimento reduzido do sistema.
