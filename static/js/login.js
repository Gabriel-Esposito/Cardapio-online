document.getElementById('form-login').addEventListener('submit', async (ev)=>{
  ev.preventDefault();const form=ev.currentTarget;
  const mensagem=document.getElementById('login-mensagem');mensagem.textContent='Entrando...';
  try {
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({usuario:form.elements.namedItem('usuario').value,senha:form.elements.namedItem('senha').value})});
    const data=await r.json();if(!r.ok)throw new Error(data.erro||'Erro no login');
    window.location.assign(data.redirecionar);
  } catch(err){mensagem.textContent=err.message;}
});
