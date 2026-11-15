const $ = (id) => document.getElementById(id);
const dinheiro = (n) => Number(n).toLocaleString('pt-BR', {style:'currency', currency:'BRL'});
let produtos = [], categoria = 0;
const carrinho = new Map();
let intervalosImagens = [];
$('ano').textContent = new Date().getFullYear();

function elemento(tag, classe, texto) {
  const el = document.createElement(tag);
  if (classe) el.className = classe;
  if (texto !== undefined) el.textContent = texto;
  return el;
}
function abrirCarrinho(aberto) {
  $('painel-carrinho').classList.toggle('open', aberto);
  $('overlay').classList.toggle('hidden', !aberto);
  $('painel-carrinho').setAttribute('aria-hidden', String(!aberto));
  $('botao-carrinho').setAttribute('aria-expanded', String(aberto));
}
$('botao-carrinho').addEventListener('click', () => abrirCarrinho(true));
$('fechar-carrinho').addEventListener('click', () => abrirCarrinho(false));
$('overlay').addEventListener('click', () => abrirCarrinho(false));

function renderProdutos() {
  const termo = $('busca').value.toLocaleLowerCase('pt-BR').trim();
  const filtrados = produtos.filter(p => (!categoria || p.categoria_id === categoria) &&
    (p.nome + ' ' + p.descricao).toLocaleLowerCase('pt-BR').includes(termo));
  intervalosImagens.forEach(clearInterval);
  intervalosImagens = [];
  $('grade-produtos').replaceChildren();
  $('mensagem-cardapio').textContent = filtrados.length ? '' : 'Nenhum doce encontrado.';
  for (const p of filtrados) {
    const card = elemento('article', 'product');
    const art=elemento('div','product-art');
    if(p.imagens.length){
      let atual=0;const img=document.createElement('img');img.alt=`Imagem de ${p.nome}`;img.src=`/api/imagens/${p.imagens[0]}`;art.append(img);
      if(p.imagens.length>1){
        const trocarImagem=(delta)=>{atual=(atual+delta+p.imagens.length)%p.imagens.length;img.src=`/api/imagens/${p.imagens[atual]}`;};
        let intervalo=setInterval(()=>trocarImagem(1),3000);
        intervalosImagens.push(intervalo);
        const controles=elemento('div','image-controls');
        for(const [texto,delta] of [['‹',-1],['›',1]]){
          const btn=elemento('button','',texto);btn.type='button';btn.setAttribute('aria-label',delta<0?'Imagem anterior':'Próxima imagem');
          btn.addEventListener('click',()=>{
            trocarImagem(delta);
            clearInterval(intervalo);
            const indice=intervalosImagens.indexOf(intervalo);
            intervalo=setInterval(()=>trocarImagem(1),3000);
            intervalosImagens[indice]=intervalo;
          });controles.append(btn);
        }
        art.append(controles);
      }
    }else art.textContent=p.categoria_emoji;
    card.append(art);
    const body = elemento('div', 'product-body');
    body.append(elemento('span', 'product-category', p.categoria), elemento('h3', '', p.nome), elemento('p', '', p.descricao));
    const bottom = elemento('div', 'product-bottom');
    const btn = elemento('button', 'btn primary', '+ Adicionar');
    btn.addEventListener('click', () => {carrinho.set(p.id, Math.min(99,(carrinho.get(p.id)||0)+1)); renderCarrinho(); abrirCarrinho(true);});
    bottom.append(elemento('strong', 'price', dinheiro(p.preco)), btn); body.append(bottom); card.append(body); $('grade-produtos').append(card);
  }
}
function renderCategorias(categorias) {
  $('categorias').replaceChildren();
  for (const cat of [{id:0,nome:'Todos'}, ...categorias]) {
    const btn = elemento('button', 'filter' + (cat.id===categoria?' selected':''), cat.nome);
    btn.addEventListener('click',()=>{categoria=cat.id;renderCategorias(categorias);renderProdutos();});
    $('categorias').append(btn);
  }
}
function renderCarrinho() {
  $('itens-carrinho').replaceChildren(); let total=0, count=0;
  for (const [id, qtd] of carrinho) {
    const p = produtos.find(x=>x.id===id); if(!p) { carrinho.delete(id); continue; }
    total += p.preco*qtd; count+=qtd;
    const row=elemento('div','cart-row'), info=elemento('div'), ctr=elemento('div','qty-controls');
    info.append(elemento('strong','',p.nome),elemento('small','',dinheiro(p.preco*qtd)));
    for(const [sinal,delta] of [['−',-1],['+',1]]) {
      const b=elemento('button','',sinal); b.type='button'; b.setAttribute('aria-label',delta===1?'Aumentar':'Diminuir');
      b.addEventListener('click',()=>{const next=qtd+delta;if(next<1)carrinho.delete(id);else carrinho.set(id,Math.min(99,next));renderCarrinho();});ctr.append(b);
      if(delta===-1)ctr.append(elemento('span','',String(qtd)));
    }
    row.append(info,ctr);$('itens-carrinho').append(row);
  }
  if(!count)$('itens-carrinho').append(elemento('p','muted','Seu carrinho está vazio. Adicione um doce!'));
  $('contador').textContent=String(count);$('total').textContent=dinheiro(total);
  $('form-pedido').querySelector('button[type=submit]').disabled=count===0;
}
$('busca').addEventListener('input',renderProdutos);
$('form-pedido').addEventListener('submit',async(ev)=>{
  ev.preventDefault(); if(!carrinho.size)return;
  const form=ev.currentTarget;
  const botao=form.querySelector('button[type=submit]'); botao.disabled=true;
  $('mensagem-pedido').textContent='Enviando pedido...';
  try {
    const response=await fetch('/api/pedidos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      cliente:$('cliente').value,telefone:$('telefone').value,observacao:$('observacao').value,forma_pagamento:$('forma-pagamento').value,
      itens:[...carrinho].map(([id,quantidade])=>({id,quantidade}))})});
    const data=await response.json(); if(!response.ok)throw new Error(data.erro||'Não foi possível enviar.');
    carrinho.clear();renderCarrinho();form.reset();
    $('mensagem-pedido').textContent=`Pedido #${data.pedido_id} registrado com sucesso! Total: ${dinheiro(data.total)}.`;
  } catch(err) {$('mensagem-pedido').textContent=err.message;}
  finally {botao.disabled=carrinho.size===0;}
});
$('form-historico').addEventListener('submit',async(ev)=>{
  ev.preventDefault();
  const form=ev.currentTarget, botao=form.querySelector('button[type=submit]');
  const lista=$('lista-meus-pedidos');
  botao.disabled=true;
  lista.replaceChildren();
  $('historico-mensagem').textContent='Buscando seus pedidos...';
  try {
    const response=await fetch('/api/meus-pedidos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      cliente:$('historico-nome').value,telefone:$('historico-telefone').value})});
    const pedidos=await response.json();
    if(!response.ok)throw new Error(pedidos.erro||'Não foi possível consultar os pedidos.');
    if(!pedidos.length) {
      $('historico-mensagem').textContent='Nenhum pedido encontrado com esses dados.';
      return;
    }
    $('historico-mensagem').textContent=`${pedidos.length} pedido(s) encontrado(s).`;
    for(const pedido of pedidos) {
      const card=elemento('article','order'), topo=elemento('div','order-top');
      topo.append(elemento('strong','',`Pedido #${pedido.id} · ${pedido.criado_em}`),
        elemento('strong','order-status',pedido.status));
      card.append(topo);
      const itens=elemento('ul');
      for(const item of pedido.itens)
        itens.append(elemento('li','',`${item.quantidade} × ${item.nome_produto} — ${dinheiro(item.subtotal)}`));
      card.append(itens,elemento('p','muted',`Pagamento: ${pedido.forma_pagamento||'Não informado'} · Total: ${dinheiro(pedido.total)}`));
      if(pedido.observacao)card.append(elemento('small','muted',`Observação: ${pedido.observacao}`));
      lista.append(card);
    }
  } catch(err) {$('historico-mensagem').textContent=err.message;}
  finally {botao.disabled=false;}
});
(async function iniciar(){
  try {
    const [a,b]=await Promise.all([fetch('/api/produtos'),fetch('/api/categorias')]);
    if(!a.ok||!b.ok)throw new Error('Banco de dados indisponível.');
    produtos=await a.json();renderCategorias(await b.json());renderProdutos();renderCarrinho();
  } catch(err){$('mensagem-cardapio').textContent='Não foi possível carregar o cardápio. Verifique o servidor e o MySQL.';}
})();
