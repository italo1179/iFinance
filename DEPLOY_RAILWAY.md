# 🚀 Deploy do iFinance no Railway

## 📋 Pré-requisitos

1. Conta no GitHub (gratuita)
2. Conta no Railway (gratuita - $5 crédito/mês)
3. Git instalado

---

## 🔧 Passo 1: Preparar o Repositório GitHub

### 1.1 Inicializar Git (se ainda não fez)
```bash
cd "F:\iFinance Web"
git init
git add .
git commit -m "Initial commit - iFinance Web"
```

### 1.2 Criar repositório no GitHub
1. Acesse: https://github.com/new
2. Nome: `ifinance-web`
3. Marque: **Private** (para manter privado)
4. Clique: **Create repository**

### 1.3 Enviar código para o GitHub
```bash
git remote add origin https://github.com/SEU_USUARIO/ifinance-web.git
git branch -M main
git push -u origin main
```

---

## 🚂 Passo 2: Deploy no Railway

### 2.1 Criar conta
1. Acesse: https://railway.app
2. Clique: **Login**
3. Use: **GitHub** para login
4. Autorize o Railway

### 2.2 Criar novo projeto
1. No dashboard, clique: **New Project**
2. Selecione: **Deploy from GitHub repo**
3. Escolha: `ifinance-web`
4. Clique: **Deploy Now**

### 2.3 Adicionar PostgreSQL
1. No projeto, clique: **New**
2. Selecione: **Database**
3. Escolha: **PostgreSQL**
4. Aguarde provisionar (~30 segundos)

### 2.4 Configurar Variáveis de Ambiente

Clique no serviço do app → **Variables** → Adicione:

```
SECRET_KEY=seu-secret-key-super-secreto-aqui-123456
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

**Para gerar SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2.5 Conectar Database ao App

1. Clique no serviço PostgreSQL
2. Copie a variável `DATABASE_URL`
3. No serviço do app, adicione a variável conforme acima

---

## ✅ Passo 3: Verificar Deploy

1. Railway vai fazer o build automático
2. Aguarde ~2-5 minutos
3. Clique em **Settings** → Veja a **URL pública**
4. Acesse: `https://seu-app.railway.app`

---

## 🔐 Passo 4: Criar Primeira Conta

1. Acesse sua URL
2. Clique: **Criar conta**
3. Cadastre-se!

---

## 📊 Monitorar Uso

### Ver quanto gastou dos $5:
1. No Railway, vá em **Usage**
2. Veja o gráfico de consumo
3. Previsão do mês

### Custo esperado:
- **App pequeno**: $3-4/mês
- **Bem dentro do grátis!** ✅

---

## 🔄 Atualizar o App (depois de mudanças)

```bash
git add .
git commit -m "Descrição da mudança"
git push
```

Railway detecta e faz **deploy automático**! 🚀

---

## 🛠️ Comandos Úteis

### Ver logs do app:
No Railway → Seu app → **Deployments** → Último deploy → **View Logs**

### Reiniciar app:
**Settings** → **Restart**

### Fazer backup do banco:
**PostgreSQL** → **Backups** → **Create Backup**

---

## ⚠️ Troubleshooting

### App não inicia?
- Verifique logs
- Confirme que `DATABASE_URL` está configurada
- Verifique se `SECRET_KEY` existe

### Erro de migração do banco?
O app cria as tabelas automaticamente na primeira execução.

### Fotos de perfil não aparecem?
Normal! Railway não persiste arquivos. Solução:
- Use serviço externo (Cloudinary, AWS S3)
- Por enquanto, as fotos funcionam mas podem ser perdidas em redeploy

---

## 💰 Otimizar Custos

Se quiser gastar MENOS dos $5:

1. **Desligar quando não usar:**
   - Settings → Sleep app when inactive
   
2. **Usar banco menor:**
   - Já está otimizado!

---

## 🎉 Pronto!

Seu iFinance está no ar! 🚀

**URL:** `https://seu-app.railway.app`

---

## 📞 Suporte

Problemas? 
- Documentação Railway: https://docs.railway.app
- GitHub Issues: Crie uma issue no seu repo
