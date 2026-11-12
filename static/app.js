// Python corrige o quiz. O navegador só mostra o jogo e guarda suas respostas.
const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="dispatch-token"]').content;
const STORAGE_KEY = 'orbit-dispatch-quiz-v1';
const choices = [$('choice-a'), $('choice-b')];
let game = null;
let showFeedback = false;
let busy = false;
let stopped = false;

function setBusy(value) {
  busy = value;
  choices.forEach((button) => { button.disabled = value || stopped || !game || showFeedback || game.concluido; });
  $('next').disabled = value || stopped || !game || !showFeedback;
  $('stop').disabled = value || stopped || !game;
  $('reset').disabled = value || stopped;
  $('retry').disabled = value || stopped;
  $('review-last').disabled = value || stopped;
  $('play-again').disabled = value || stopped;
  ['confirm-stop','cancel-stop','confirm-reset','cancel-reset'].forEach((id) => { $(id).disabled = value || stopped; });
  $('case-body').setAttribute('aria-busy', String(value));
}

function focusResult(element) {
  element.focus({preventScroll:true});
  element.scrollIntoView({block:'nearest', behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
}

async function request(path, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(),8000);
  try {
    const response = await fetch(path, {
      method:'POST', cache:'no-store', signal:controller.signal,
      headers:{'Content-Type':'application/json','X-Dispatch-Token':token},
      body:JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.erro || 'O pedido não foi aceito.');
    return data;
  } catch (error) {
    if (error instanceof TypeError || error.name === 'AbortError') {
      throw new Error('O Python não respondeu. Confira se o servidor está rodando. No Docker, use docker compose up -d e recarregue a página. Seu progresso salvo não foi alterado.');
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function readProgress() {
  let raw;
  try { raw = localStorage.getItem(STORAGE_KEY); }
  catch {
    $('storage-status').textContent = 'O navegador bloqueou o armazenamento. Esta rodada dura enquanto a página ficar aberta.';
    return {respostas:[],feedback:false};
  }
  if (raw === null) return {respostas:[],feedback:false};
  try {
    const saved = JSON.parse(raw);
    if (!saved || !Array.isArray(saved.respostas) || typeof saved.feedback !== 'boolean') throw new Error();
    return saved;
  } catch {
    throw new Error('Não consegui ler o progresso salvo. Use “Recomeçar” se quiser iniciar uma rodada nova. Nada foi apagado.');
  }
}

function saveProgress() {
  try {
    localStorage.setItem(STORAGE_KEY,JSON.stringify({respostas:game.respostas,feedback:showFeedback}));
    $('storage-status').textContent = 'Progresso salvo neste navegador.';
  } catch {
    $('storage-status').textContent = 'Não foi possível salvar. Você pode jogar, mas esta rodada pode se perder ao fechar ou recarregar.';
  }
}

function renderExchange(path,payload,data) {
  if (!data.ultima) {
    $('exchange').hidden = true;
    $('study-empty').hidden = false;
    return;
  }
  // São campos do JSON real, não uma simulação de rede.
  const sent = path === 'api/responder' ? {pergunta:payload.pergunta,escolha:payload.escolha} : {respostas:payload.respostas};
  const received = {respondidas:data.respondidas,acertos:data.acertos,concluido:data.concluido,ultima:{acertou:data.ultima.acertou,correta:data.ultima.correta,explicacao:data.ultima.explicacao}};
  $('request-json').textContent = JSON.stringify(sent,null,2);
  $('response-json').textContent = JSON.stringify(received,null,2);
  $('http-status').textContent = `POST /${path} → HTTP 200. ${path === 'api/jogo' ? 'O Python conferiu o progresso recuperado do navegador.' : 'O Python recebeu a escolha e devolveu a correção.'}`;
  $('exchange').hidden = false;
  $('study-empty').hidden = true;
}

function renderScene(level, completed) {
  $('game-board').dataset.level = String(level.numero);
  $('scene-level').textContent = `NÍVEL ${level.numero}`;
  $('scene-name').textContent = level.nome;
  $('scene-caption').textContent = [
    'Primeiro o básico. Depois a decolagem.',
    'Já saiu do chão. Agora vai.',
    'Longe da Terra. Perto do deploy.'
  ][level.numero - 1];
  for (const item of game.niveis) {
    const dot = $(`orbit-${item.numero}`);
    dot.classList.toggle('current',item.numero === level.numero);
    dot.classList.toggle('done',item.numero < level.numero || completed);
    if (item.numero === level.numero) dot.setAttribute('aria-current','step');
    else dot.removeAttribute('aria-current');
  }
  const unlocked = showFeedback && game.ultima.nivel_concluido;
  $('level-reward').hidden = !unlocked && !completed;
  if (unlocked || completed) {
    $('level-message').textContent = game.concluido ? 'As três órbitas estão completas' : 'Nova órbita liberada!';
    $('unlock-name').textContent = game.concluido ? 'Missão cumprida ✦' : `Nível ${game.ultima.proximo_nivel.numero}`;
  }
}

function celebrateAnswer() {
  const scene = $('scene');
  scene.classList.remove('pulse','celebrate');
  $('confetti').replaceChildren();
  $('reward').textContent = game.ultima.acertou ? '+1 ✦' : '↗';
  // Reinicia a animação visual. Isso não altera os pontos nem o progresso.
  void scene.offsetWidth;
  scene.classList.add(game.ultima.nivel_concluido ? 'celebrate' : 'pulse');
  if (game.ultima.nivel_concluido && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    for (let i=0;i<20;i++) {
      const piece = document.createElement('i');
      piece.style.setProperty('--x',`${(i*37)%100}%`);
      piece.style.setProperty('--c',['#d1f570','#dcc9ff','#f1a37a','#fff8e5'][i%4]);
      piece.style.setProperty('--r',`${120+i*29}deg`);
      piece.style.setProperty('--d',`${(i%5)*.07}s`);
      $('confetti').append(piece);
    }
  }
}

function renderGame() {
  $('progress-text').textContent = `${game.respondidas} / ${game.total}`;
  $('score').textContent = String(game.acertos);
  $('mission-progress').max = game.total;
  $('mission-progress').value = game.respondidas;
  $('mission-progress').textContent = `${game.respondidas} de ${game.total}`;
  $('server-status').textContent = 'Servidor ligado';
  $('retry').hidden = true;
  const finished = game.concluido && !showFeedback;
  $('skip-game').href = finished ? '#finish-title' : '#case-title';
  $('skip-game').textContent = finished ? 'Ir para o resultado' : 'Ir para a pergunta';
  $('finish').hidden = !finished;
  $('ticket').hidden = finished;
  $('why').open = false;
  if (finished) {
    renderScene(game.niveis[game.niveis.length-1],true);
    $('final-score').textContent = `${game.acertos} de ${game.total} acertos.`;
    $('level-scores').replaceChildren(...game.resumo.map((level) => {
      const item = document.createElement('li');
      item.textContent = `Nível ${level.numero}: ${level.acertos} de ${level.respondidas} acertos.`;
      return item;
    }));
    setBusy(busy);
    return;
  }
  const question = showFeedback ? game.ultima.pergunta : game.pergunta;
  const level = game.niveis.find((item) => item.numero === question.nivel);
  const position = showFeedback ? (game.respondidas-1)%game.por_nivel+1 : game.respondidas%game.por_nivel+1;
  renderScene(level,false);
  $('question-number').textContent = `${position} / ${game.por_nivel}`;
  $('case-tag').textContent = question.titulo;
  $('case-title').textContent = question.enunciado;
  $('case-situation').textContent = question.contexto;
  const answeredInLevel = showFeedback ? position : position-1;
  $('level-dots').replaceChildren(...Array.from({length:game.por_nivel},(_,index) => {
    const dot = document.createElement('span');
    dot.classList.toggle('filled',index < answeredInLevel);
    return dot;
  }));
  question.opcoes.forEach((option) => {
    $(`label-${option.id}`).textContent = option.texto;
    const button = $(`choice-${option.id}`);
    const selected = showFeedback && game.ultima.escolha === option.id;
    const correct = showFeedback && game.ultima.correta === option.id;
    button.setAttribute('aria-pressed',String(selected));
    button.classList.toggle('answered',showFeedback);
    button.classList.toggle('correct',correct);
    button.classList.toggle('incorrect',selected && !game.ultima.acertou);
    button.querySelector('.choice-mark').textContent = correct ? '✓' : (selected ? '×' : '');
  });
  $('result').hidden = !showFeedback;
  $('next').hidden = !showFeedback;
  $('next').classList.toggle('level-next',showFeedback && game.ultima.nivel_concluido);
  if (showFeedback) {
    const feedback = game.ultima;
    const correct = question.opcoes.find((option) => option.id === feedback.correta);
    $('result-title').textContent = feedback.acertou ? 'Boa! ✦' : 'Quase.';
    $('answer-verdict').textContent = feedback.acertou ? '+1 acerto.' : `Era ${feedback.correta.toUpperCase()}: ${correct.texto}`;
    $('result-text').textContent = feedback.explicacao;
    $('source').href = feedback.fonte;
    $('next').textContent = game.concluido ? 'Ver meu placar →' : (feedback.nivel_concluido ? `Subir para o nível ${feedback.proximo_nivel.numero} ↑` : 'Próxima →');
  }
  setBusy(busy);
}

async function start() {
  if (busy || stopped) return;
  setBusy(true);
  $('notice').textContent = '';
  try {
    const saved = readProgress();
    const payload = {respostas:saved.respostas};
    game = await request('api/jogo',payload);
    showFeedback = saved.feedback && Boolean(game.ultima);
    renderExchange('api/jogo',payload,game);
    renderGame();
    if (saved.respostas.length) $('storage-status').textContent = 'De volta de onde você parou.';
  } catch (error) {
    $('notice').textContent = error.message;
    $('server-status').textContent = 'Falha ao carregar';
    $('retry').hidden = false;
  } finally { setBusy(false); }
}

async function answer(choice) {
  if (busy || stopped || !game || showFeedback || game.concluido) return;
  setBusy(true);
  $('notice').textContent = '';
  const payload = {respostas:game.respostas,pergunta:game.pergunta.id,escolha:choice};
  try {
    game = await request('api/responder',payload);
    showFeedback = true;
    saveProgress();
    renderExchange('api/responder',payload,game);
    renderGame();
    celebrateAnswer();
    focusResult($('result'));
  } catch (error) { $('notice').textContent = error.message; }
  finally { setBusy(false); }
}

choices.forEach((button) => button.addEventListener('click',() => answer(button.dataset.choice)));
$('retry').addEventListener('click',start);
$('next').addEventListener('click',() => {
  if (busy || stopped || !showFeedback) return;
  showFeedback = false;
  saveProgress();
  renderGame();
  focusResult(game.concluido ? $('finish') : $('case-title'));
});
$('review-last').addEventListener('click',() => {
  if (busy || stopped || !game.ultima) return;
  showFeedback = true;
  saveProgress();
  renderGame();
  focusResult($('result'));
});
$('play-again').addEventListener('click',() => {
  $('reset-error').textContent = '';
  $('reset-dialog').showModal();
});

for (const kind of ['stop','reset']) {
  $(kind).addEventListener('click',() => {
    $(`${kind}-error`).textContent = '';
    $(`${kind}-dialog`).showModal();
  });
  $(`${kind}-dialog`).addEventListener('cancel',(event) => { if (busy) event.preventDefault(); });
  $(`cancel-${kind}`).addEventListener('click',() => $(`${kind}-dialog`).close());
}
$('confirm-reset').addEventListener('click',async () => {
  if (busy || stopped) return;
  setBusy(true);
  try {
    const payload = {respostas:[]};
    game = await request('api/jogo',payload);
    showFeedback = false;
    saveProgress();
    renderExchange('api/jogo',payload,game);
    renderGame();
    $('notice').textContent = '';
    $('reset-dialog').close();
    focusResult($('case-title'));
  } catch (error) { $('reset-error').textContent = error.message; }
  finally { setBusy(false); }
});
$('confirm-stop').addEventListener('click',async () => {
  if (busy || stopped) return;
  setBusy(true);
  try {
    await request('api/parar',{});
    stopped = true;
    $('server-status').textContent = 'Central fechada';
    $('status-dot').classList.add('closed');
    $('stop-dialog').close();
    $('restart-panel').hidden = false;
    focusResult($('restart-panel'));
  } catch (error) { $('stop-error').textContent = error.message; }
  finally { setBusy(false); }
});
$('reconnect').addEventListener('click',() => location.reload());
start();
