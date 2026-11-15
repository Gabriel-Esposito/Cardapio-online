const $=id=>document.getElementById(id);
const csrf=document.querySelector('meta[name="csrf-token"]').content;
const moeda=n=>Number(n).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const make=(tag,txt,classe)=>{const e=document.createElement(tag);if(txt!==undefined)e.textContent=txt;if(classe)e.className=classe;return e;};
let produtos=[], categorias=[], imagensAtuais=[];
async function api(path,method='GET',body) {
  const opts={method,headers:{'X-CSRF-Token':csrf}};
  if(body!==undefined){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body);}
  const res=await fetch(path,opts);const data=await res.json();if(!res.ok)throw new Error(data.erro||'Erro de comunicação');return data;
}
async function carregarDashboard(){
  const d=await api('/api/dashboard');
  $('total-espera').textContent=d.espera;$('total-ativos').textContent=d.ativos;$('total-atendidos').textContent=d.atendidos;
  if($('total-faturamento'))$('total-faturamento').textContent=moeda(d.faturamento);
  $('dashboard-mensagem').textContent='';
}
function alternarAba(aba){
  document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===aba));
  document.querySelectorAll('main > section').forEach(s=>s.classList.toggle('hidden',s.id!==`tab-${aba}`));
  if(aba==='dashboard')carregarDashboard().catch(err=>$('dashboard-mensagem').textContent=err.message);
  if(aba==='pedidos'||aba==='historico')carregarPedidos().catch(err=>alert(err.message));
  if(aba==='produtos')carregarProdutos().catch(err=>alert(err.message));
  if(aba==='usuarios')carregarUsuarios().catch(err=>$('usuarios-mensagem').textContent=err.message);
}
document.querySelectorAll('[data-tab]').forEach(btn=>btn.addEventListener('click',()=>alternarAba(btn.dataset.tab)));
function limpar(){
  $('form-produto').reset();$('produto-id').value='';$('titulo-form').textContent='Novo produto';
  imagensAtuais=[];$('imagens-atuais').replaceChildren();$('campo-imagens').classList.add('hidden');
  $('produto-mensagem').textContent='';
}
function renderImagens(){
  const area=$('imagens-atuais');area.replaceChildren();
  for(const id of imagensAtuais){
    const linha=make('div',undefined,'imagem-atual'), img=document.createElement('img'), remover=make('button','Remover');
    img.src=`/api/imagens/${id}`;img.alt='Imagem atual do produto';remover.type='button';
    remover.addEventListener('click',()=>{imagensAtuais=imagensAtuais.filter(i=>i!==id);renderImagens();});
    linha.append(img,remover);area.append(linha);
  }
}
function editar(p){
  limpar();$('produto-id').value=p.id;$('nome').value=p.nome;$('categoria').value=p.categoria_id;
  $('preco').value=p.preco;$('custo').value=p.custo===null?'':p.custo;$('emoji').value=p.emoji;
  $('descricao').value=p.descricao;$('disponivel').checked=!!p.disponivel;$('titulo-form').textContent='Editar produto';
  imagensAtuais=[...p.imagens];$('sem-capa').checked=!imagensAtuais.length;
  $('campo-imagens').classList.toggle('hidden',$('sem-capa').checked);renderImagens();
  $('modal-produto').showModal();$('nome').focus();
}
async function carregarProdutos(){
  [produtos,categorias]=await Promise.all([api('/api/produtos'),api('/api/categorias')]);
  const selecionada=$('categoria').value;$('categoria').replaceChildren();
  for(const c of categorias){const opt=make('option',c.nome);opt.value=c.id;$('categoria').append(opt);}
  if(selecionada)$('categoria').value=selecionada;
  $('tabela-produtos').replaceChildren();
  for(const p of produtos){
    const tr=make('tr');for(const val of [p.emoji+' '+p.nome,p.categoria,moeda(p.preco),p.disponivel?'Sim':'Não'])tr.append(make('td',val));
    const actions=make('td'), edit=make('button','Editar'), del=make('button','Excluir');
    edit.addEventListener('click',()=>editar(p));
    del.addEventListener('click',async()=>{if(!confirm(`Excluir ${p.nome}?`))return;
      try{await api(`/api/produtos/${p.id}`,'DELETE');await carregarProdutos();}catch(err){alert(err.message);}});
    actions.append(edit,del);tr.append(actions);$('tabela-produtos').append(tr);
  }
}
function lerImagem(file){
  return new Promise((resolve,reject)=>{
    const reader=new FileReader();reader.onload=()=>resolve(reader.result);
    reader.onerror=()=>reject(new Error('Não foi possível ler a imagem.'));reader.readAsDataURL(file);
  });
}
function limparUsuario(){
  $('form-usuario').reset();$('usuario-id').value='';$('titulo-usuario').textContent='Cadastrar usuário';
  $('senha').required=true;$('senha-ajuda').classList.add('hidden');
  $('salvar-usuario').textContent='Cadastrar';$('cancelar-usuario').classList.add('hidden');
  $('usuario-mensagem').textContent='';
}
async function carregarUsuarios(){
  const usuarios=await api('/api/usuarios');
  const tabela=$('tabela-usuarios');tabela.replaceChildren();
  $('usuarios-mensagem').textContent=usuarios.length?'':'Nenhum usuário cadastrado.';
  for(const usuario of usuarios){
    const tr=make('tr'), actions=make('td'), edit=make('button','Editar');
    tr.append(make('td',usuario.usuario),make('td',usuario.perfil==='admin'?'Administrador':'Funcionário'));
    edit.type='button';edit.addEventListener('click',()=>{
      limparUsuario();$('usuario-id').value=usuario.id;$('usuario').value=usuario.usuario;
      $('perfil').value=usuario.perfil;$('senha').required=false;$('senha-ajuda').classList.remove('hidden');
      $('titulo-usuario').textContent='Editar usuário';$('salvar-usuario').textContent='Salvar alterações';
      $('cancelar-usuario').classList.remove('hidden');$('usuario').focus();
    });
    actions.append(edit);tr.append(actions);tabela.append(tr);
  }
}
if($('form-produto')){
  $('novo-produto').addEventListener('click',()=>{limpar();$('modal-produto').showModal();$('nome').focus();});
  $('cancelar-edicao').addEventListener('click',()=>$('modal-produto').close());
  $('sem-capa').addEventListener('change',()=>$('campo-imagens').classList.toggle('hidden',$('sem-capa').checked));
  $('form-produto').addEventListener('submit',async(ev)=>{
    ev.preventDefault();const id=$('produto-id').value, files=[...$('imagens').files];
    try{
      if(!$('sem-capa').checked && (!imagensAtuais.length&&!files.length || imagensAtuais.length+files.length>3))
        throw new Error('Selecione entre 1 e 3 imagens ou escolha sem capa.');
      if(!$('sem-capa').checked && files.some(f=>f.size>2*1024*1024||!['image/png','image/jpeg','image/gif'].includes(f.type)))
        throw new Error('Use imagens PNG, JPEG ou GIF de até 2 MB.');
      const imagens=$('sem-capa').checked?[]:[...imagensAtuais,...await Promise.all(files.map(lerImagem))];
      const data={nome:$('nome').value,categoria_id:Number($('categoria').value),preco:$('preco').value,custo:$('custo').value,emoji:$('emoji').value,descricao:$('descricao').value,disponivel:$('disponivel').checked,imagens};
      await api(id?`/api/produtos/${id}`:'/api/produtos',id?'PUT':'POST',data);
    }catch(err){$('produto-mensagem').textContent=err.message;return;}
    $('modal-produto').close();limpar();
    try{await carregarProdutos();}catch(err){alert(err.message);}
  });
  $('cancelar-usuario').addEventListener('click',limparUsuario);
  $('form-usuario').addEventListener('submit',async ev=>{
    ev.preventDefault();const id=$('usuario-id').value;
    let result;
    try{result=await api(id?`/api/usuarios/${id}`:'/api/usuarios',id?'PUT':'POST',
      {usuario:$('usuario').value,senha:$('senha').value,perfil:$('perfil').value});}
    catch(err){$('usuario-mensagem').textContent=err.message;return;}
    if(id && result.perfil_atual==='funcionario'){window.location.reload();return;}
    limparUsuario();$('usuario-mensagem').textContent=id?'Usuário atualizado.':'Usuário cadastrado.';
    try{await carregarUsuarios();}catch(err){$('usuarios-mensagem').textContent=err.message;}
  });
}
async function carregarPedidos(){
  const pedidos=await api('/api/pedidos');
  for(const [id,finalizados] of [['lista-pedidos',false],['lista-historico',true]]){
    const lista=$(id);lista.replaceChildren();
    const filtrados=pedidos.filter(p=>['Concluído','Cancelado'].includes(p.status)===finalizados);
    if(!filtrados.length){lista.append(make('p','Nenhum pedido encontrado.','muted'));continue;}
    for(const p of filtrados){
      const article=make('article',undefined,'order'),top=make('div',undefined,'order-top'),titulo=make('div');
      titulo.append(make('strong',`Pedido #${p.id} · ${p.cliente}`),make('div',`${p.criado_em} · ${p.telefone}`,'muted'));
      const select=make('select');select.setAttribute('aria-label',`Status do pedido ${p.id}`);
      for(const s of ['Recebido','Preparando','Concluído','Cancelado']){
        const op=make('option',s);op.value=s;op.selected=p.status===s;select.append(op);
      }
      select.addEventListener('change',async()=>{
        try{await api(`/api/pedidos/${p.id}/status`,'PATCH',{status:select.value});}
        catch(err){alert(err.message);try{await carregarPedidos();}catch(reloadError){alert(reloadError.message);}return;}
        try{await Promise.all([carregarPedidos(),carregarDashboard()]);}
        catch(err){alert(err.message);}
      });
      top.append(titulo,select);article.append(top);
      const ul=make('ul');for(const i of p.itens)ul.append(make('li',`${i.quantidade}× ${i.nome_produto} — ${moeda(i.subtotal)}`));
      article.append(ul,make('strong',`Total: ${moeda(p.total)}`),make('p',`Pagamento: ${p.forma_pagamento||'Não informado'}`,'muted'));
      if(p.observacao)article.append(make('p',`Observação: ${p.observacao}`,'muted'));
      lista.append(article);
    }
  }
}
document.querySelectorAll('[data-recarregar-pedidos]').forEach(btn=>btn.addEventListener('click',()=>carregarPedidos().catch(err=>alert(err.message))));
$('recarregar-dashboard').addEventListener('click',()=>carregarDashboard().catch(err=>$('dashboard-mensagem').textContent=err.message));
$('sair').addEventListener('click',async()=>{try{await api('/api/logout','POST');window.location.assign('/login');}catch(err){alert(err.message);}});
carregarDashboard().catch(err=>$('dashboard-mensagem').textContent=err.message);
