# ✅ Checklist de Deploy no Railway

## 📦 Arquivos Criados
- [x] `Procfile` - Comando para iniciar o app
- [x] `runtime.txt` - Versão do Python
- [x] `.gitignore` - Arquivos a ignorar
- [x] `railway.json` - Configurações do Railway
- [x] `requirements.txt` - Dependências Python
- [x] `DEPLOY_RAILWAY.md` - Guia completo
- [x] `gerar_secret_key.py` - Gerar SECRET_KEY

## 🔑 Sua SECRET_KEY

```
226256cc7177d2b651ffb805e14390eb99ec77d28de9de922631b8a854135ee8
```

**⚠️ IMPORTANTE:** Guarde essa chave em segredo!

---

## 🚀 Passos Rápidos (Resumo)

### 1️⃣ GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/SEU_USUARIO/ifinance-web.git
git push -u origin main
```

### 2️⃣ Railway
1. Login: https://railway.app (com GitHub)
2. New Project → Deploy from GitHub → Selecione o repo
3. Add Database → PostgreSQL
4. Variables → Adicione:
   - `SECRET_KEY` = (cole a chave acima)
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`

### 3️⃣ Aguarde o Deploy
- 2-5 minutos ⏱️
- Acesse sua URL!

---

## 📱 Depois do Deploy

✅ Criar sua conta
✅ Testar cadastro de transações
✅ Verificar salários
✅ Testar categorias

---

## 🔗 Links Úteis

- **Railway Dashboard:** https://railway.app/dashboard
- **Docs:** https://docs.railway.app
- **Status:** https://status.railway.app

---

## 💰 Monitoramento

- Acesse Railway → Usage
- Veja gasto mensal
- Normal: $3-4/mês (dentro do grátis!)

---

## 🎉 Pronto!

Leia o arquivo **DEPLOY_RAILWAY.md** para detalhes completos!
