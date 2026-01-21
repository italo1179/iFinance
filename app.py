import os
import calendar
from datetime import datetime, date
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text


# ---------------- App / Config ----------------
app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db_url = os.environ.get("DATABASE_URL")
if db_url:
    # Render às vezes fornece postgres:// e o SQLAlchemy prefere postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    # Local: SQLite
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ifinance.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# ---------------- Models ----------------
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    foto_perfil = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Categoria(db.Model):
    __tablename__ = "categorias"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    nome = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Transacao(db.Model):
    __tablename__ = "transacoes"
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    user = db.relationship("User", backref=db.backref("transacoes", lazy=True))

    # ✅ novo: categoria (nullable)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id"), nullable=True, index=True)
    categoria = db.relationship("Categoria", lazy=True)

    descricao = db.Column(db.String(255), nullable=False)
    valor_total = db.Column(db.Float, nullable=False)  # entrada +, saída -
    tipo = db.Column(db.String(20), nullable=False)    # "entrada"/"saida"
    data = db.Column(db.Date, nullable=False)

    parcelas = db.Column(db.Integer, nullable=False, default=1)
    valor_parcela = db.Column(db.Float, nullable=False)

    observacoes = db.Column(db.Text, nullable=True)
    pago = db.Column(db.Boolean, nullable=False, default=False)
    recorrente = db.Column(db.Boolean, nullable=False, default=False)  # mensalidade
    tipo_entrada = db.Column(db.String(20), nullable=True)  # 'salario', 'outros', None

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------- Helpers ----------------
def adicionar_meses(data_ref: date, n: int) -> date:
    mes = data_ref.month - 1 + n
    ano = data_ref.year + mes // 12
    mes = mes % 12 + 1
    dia = min(data_ref.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def ym_label(ano: int, mes: int) -> str:
    return f"{mes:02d}/{ano}"


def calcular_resumo_mes(transacoes, ano: int, mes: int) -> tuple[float, float, float]:
    """
    Entradas: soma valor_total (positivo) no mês.
    Saídas: soma de parcelas no mês (abs(valor_parcela)).
    """
    entradas_mes = 0.0
    saidas_mes = 0.0

    for t in transacoes:
        if t["valor_total"] > 0:
            if t["data"].year == ano and t["data"].month == mes:
                entradas_mes += t["valor_total"]
        else:
            parcelas = max(int(t.get("parcelas", 1)), 1)
            valor_parcela_pos = abs(float(t.get("valor_parcela", t["valor_total"] / parcelas)))
            recorrente = t.get("recorrente", False)

            if recorrente:
                # Mensalidade: cobra se a data do mês é >= data de início
                data_inicio = t["data"]
                data_mes = date(ano, mes, 1)
                if data_mes >= date(data_inicio.year, data_inicio.month, 1):
                    saidas_mes += valor_parcela_pos
            else:
                # Parcelado normal
                for i in range(parcelas):
                    dparc = adicionar_meses(t["data"], i)
                    if dparc.year == ano and dparc.month == mes:
                        saidas_mes += valor_parcela_pos

    saldo_mes = entradas_mes - saidas_mes
    return round(entradas_mes, 2), round(saidas_mes, 2), round(saldo_mes, 2)


def calcular_saidas_categoria_mes(transacoes, ano: int, mes: int, categoria_id: int | None) -> float:
    """
    Se categoria_id = None -> retorna saídas normais do mês.
    Se categoria_id != None -> retorna SOMENTE saídas dessa categoria no mês.
    """
    total = 0.0

    for t in transacoes:
        if t["valor_total"] >= 0:
            continue

        if categoria_id is not None and t.get("categoria_id") != categoria_id:
            continue

        parcelas = max(int(t.get("parcelas", 1)), 1)
        valor_parcela_pos = abs(float(t.get("valor_parcela", t["valor_total"] / parcelas)))
        recorrente = t.get("recorrente", False)

        if recorrente:
            # Mensalidade: cobra se o mês é >= data de início
            data_inicio = t["data"]
            data_mes = date(ano, mes, 1)
            if data_mes >= date(data_inicio.year, data_inicio.month, 1):
                total += valor_parcela_pos
        else:
            # Parcelado normal
            for i in range(parcelas):
                dparc = adicionar_meses(t["data"], i)
                if dparc.year == ano and dparc.month == mes:
                    total += valor_parcela_pos

    return round(total, 2)


def calcular_grafico(transacoes, ano: int, mes: int, meses_antes: int = 3, meses_depois: int = 9):
    inicio = adicionar_meses(date(ano, mes, 1), -meses_antes)

    labels, entradas_vals, despesas_vals = [], [], []

    for i in range(meses_antes + meses_depois + 1):
        dref = adicionar_meses(inicio, i)
        labels.append(ym_label(dref.year, dref.month))

        ent = 0.0
        des = 0.0

        for t in transacoes:
            if t["valor_total"] > 0:
                if t["data"].year == dref.year and t["data"].month == dref.month:
                    ent += t["valor_total"]
            else:
                parcelas = max(int(t.get("parcelas", 1)), 1)
                valor_parcela_pos = abs(float(t.get("valor_parcela", t["valor_total"] / parcelas)))
                recorrente = t.get("recorrente", False)

                if recorrente:
                    # Mensalidade: cobra se o mês é >= data de início
                    data_inicio = t["data"]
                    data_ref_mes = date(dref.year, dref.month, 1)
                    if data_ref_mes >= date(data_inicio.year, data_inicio.month, 1):
                        des += valor_parcela_pos
                else:
                    # Parcelado normal
                    for p in range(parcelas):
                        dp = adicionar_meses(t["data"], p)
                        if dp.year == dref.year and dp.month == dref.month:
                            des += valor_parcela_pos

        entradas_vals.append(round(ent, 2))
        despesas_vals.append(round(des, 2))

    return labels, entradas_vals, despesas_vals


def obter_transacoes_do_usuario(user_id: int, busca: str, mostrar_pagos: bool = False, 
                                 filtro_tipo: str = None, categorias_incluir: list = None, 
                                 categorias_excluir: list = None, ordenar_por: str = "data", 
                                 ordem: str = "desc"):
    """
    Retorna lista de transações + nome da categoria (se existir).
    mostrar_pagos=False: filtra somente não pagos
    mostrar_pagos=True: retorna somente pagos
    filtro_tipo: 'entrada', 'saida', ou None para ambos
    categorias_incluir: lista de IDs de categorias para incluir (se vazio, inclui todas)
    categorias_excluir: lista de IDs de categorias para excluir
    """
    q = (
        db.session.query(Transacao, Categoria)
        .outerjoin(Categoria, Transacao.categoria_id == Categoria.id)
        .filter(Transacao.user_id == user_id)
    )

    # Nunca mostrar salários nem entradas manuais na lista principal (mas mostrar NULL)
    q = q.filter(
        (Transacao.tipo_entrada == None) | 
        ((Transacao.tipo_entrada != 'salario') & (Transacao.tipo_entrada != 'entrada_manual'))
    )

    if mostrar_pagos:
        q = q.filter(Transacao.pago == True)
    else:
        q = q.filter(Transacao.pago == False)

    # Filtro por tipo
    if filtro_tipo == 'entrada':
        q = q.filter(Transacao.valor_total > 0)
    elif filtro_tipo == 'saida':
        q = q.filter(Transacao.valor_total < 0)

    # Filtro por categorias incluir
    if categorias_incluir:
        q = q.filter(Transacao.categoria_id.in_(categorias_incluir))

    # Filtro por categorias excluir (mas não excluir transações sem categoria)
    if categorias_excluir:
        q = q.filter(
            (Transacao.categoria_id == None) | 
            (~Transacao.categoria_id.in_(categorias_excluir))
        )

    if busca:
        q = q.filter(Transacao.descricao.ilike(f"%{busca}%"))

    # Aplica ordenação
    if ordenar_por == 'data':
        order_col = Transacao.data
    elif ordenar_por == 'descricao':
        order_col = Transacao.descricao
    elif ordenar_por == 'categoria':
        order_col = Categoria.nome
    elif ordenar_por == 'valor_total':
        order_col = Transacao.valor_total
    elif ordenar_por == 'parcelas':
        order_col = Transacao.parcelas
    else:
        order_col = Transacao.data

    if ordem == 'asc':
        q = q.order_by(order_col.asc(), Transacao.id.asc())
    else:
        q = q.order_by(order_col.desc(), Transacao.id.desc())

    rows = q.all()

    transacoes = []
    for r, c in rows:
        transacoes.append({
            "id": r.id,
            "descricao": r.descricao,
            "valor_total": r.valor_total,
            "tipo": r.tipo,
            "data": r.data,
            "parcelas": r.parcelas,
            "valor_parcela": r.valor_parcela,
            "categoria_id": r.categoria_id,
            "categoria_nome": c.nome if c else None,
            "observacoes": r.observacoes,
            "pago": r.pago,
            "recorrente": r.recorrente,
        })
    return transacoes


def listar_categorias(user_id: int):
    return (
        Categoria.query.filter_by(user_id=user_id)
        .order_by(Categoria.nome.asc())
        .all()
    )


# ---------------- Auth ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""

        if not nome:
            flash("Informe seu nome.", "error")
            return redirect(url_for("register"))

        if not email:
            flash("Informe um email.", "error")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("A senha deve ter no mínimo 6 caracteres.", "error")
            return redirect(url_for("register"))

        if password != password2:
            flash("As senhas não conferem.", "error")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Esse email já está cadastrado.", "error")
            return redirect(url_for("register"))

        u = User(nome=nome, email=email, password_hash=generate_password_hash(password))
        db.session.add(u)
        db.session.commit()

        login_user(u)
        flash("Conta criada com sucesso ✅", "ok")
        return redirect(url_for("home"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        u = User.query.filter_by(email=email).first()
        if not u or not check_password_hash(u.password_hash, password):
            flash("Email ou senha incorretos.", "error")
            return redirect(url_for("login"))

        login_user(u)
        flash("Bem-vindo de volta ✅", "ok")
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("login"))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        senha_atual = request.form.get("senha_atual") or ""
        nova_senha = request.form.get("nova_senha") or ""
        confirmar_senha = request.form.get("confirmar_senha") or ""

        if not nome:
            flash("Informe seu nome.", "error")
            return redirect(url_for("perfil"))

        if not email:
            flash("Informe um email.", "error")
            return redirect(url_for("perfil"))

        # Verificar se email já está em uso por outro usuário
        outro_usuario = User.query.filter_by(email=email).first()
        if outro_usuario and outro_usuario.id != current_user.id:
            flash("Este email já está sendo usado por outro usuário.", "error")
            return redirect(url_for("perfil"))

        # Upload de foto de perfil
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file and file.filename != '' and allowed_file(file.filename):
                # Criar pasta de uploads se não existir
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                
                # Gerar nome único para o arquivo
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"user_{current_user.id}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Remover foto antiga se existir
                if current_user.foto_perfil:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.foto_perfil)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Salvar nova foto
                file.save(filepath)
                current_user.foto_perfil = filename

        # Atualizar nome e email
        current_user.nome = nome
        current_user.email = email

        # Alterar senha se fornecida
        if nova_senha:
            if not senha_atual:
                flash("Informe a senha atual para alterar a senha.", "error")
                return redirect(url_for("perfil"))

            if not check_password_hash(current_user.password_hash, senha_atual):
                flash("Senha atual incorreta.", "error")
                return redirect(url_for("perfil"))

            if len(nova_senha) < 6:
                flash("A nova senha deve ter no mínimo 6 caracteres.", "error")
                return redirect(url_for("perfil"))

            if nova_senha != confirmar_senha:
                flash("As senhas não conferem.", "error")
                return redirect(url_for("perfil"))

            current_user.password_hash = generate_password_hash(nova_senha)

        db.session.commit()
        flash("Perfil atualizado com sucesso ✅", "ok")
        return redirect(url_for("perfil"))

    return render_template("perfil.html")


# ---------------- Categorias ----------------
@app.route("/categorias", methods=["POST"])
@login_required
def criar_categoria():
    nome = (request.form.get("nome") or "").strip()
    mes = request.args.get("mes", "")
    ano = request.args.get("ano", "")
    busca = request.args.get("busca", "")
    categoria_sel = request.args.get("categoria", "")

    if not nome:
        flash("Informe o nome da categoria.", "error")
        return redirect(url_for("home", mes=mes, ano=ano, categoria=categoria_sel, busca=busca))

    existe = Categoria.query.filter_by(user_id=current_user.id, nome=nome).first()
    if existe:
        flash("Essa categoria já existe.", "error")
        return redirect(url_for("home", mes=mes, ano=ano, categoria=categoria_sel, busca=busca))

    c = Categoria(user_id=current_user.id, nome=nome)
    db.session.add(c)
    db.session.commit()

    flash("Categoria criada ✅", "ok")
    return redirect(url_for("home", mes=mes, ano=ano, categoria=categoria_sel, busca=busca))


@app.route("/categorias/<int:cat_id>/excluir", methods=["POST"])
@login_required
def excluir_categoria(cat_id):
    mes = request.args.get("mes", "")
    ano = request.args.get("ano", "")
    busca = request.args.get("busca", "")
    categoria_sel = request.args.get("categoria", "")

    c = Categoria.query.filter_by(id=cat_id, user_id=current_user.id).first()
    if not c:
        flash("Categoria não encontrada.", "error")
        return redirect(url_for("home", mes=mes, ano=ano, categoria=categoria_sel, busca=busca))

    # Remove a categoria das transações
    Transacao.query.filter_by(categoria_id=cat_id).update({"categoria_id": None})
    db.session.delete(c)
    db.session.commit()

    flash("Categoria excluída ✅", "ok")
    return redirect(url_for("home", mes=mes, ano=ano, categoria=categoria_sel, busca=busca))


# ---------------- App ----------------
@app.route("/", methods=["GET", "POST"])
@login_required
def home():
    hoje = datetime.today().date()

    try:
        mes_sel = int(request.args.get("mes", hoje.month))
    except ValueError:
        mes_sel = hoje.month

    try:
        ano_sel = int(request.args.get("ano", hoje.year))
    except ValueError:
        ano_sel = hoje.year

    busca = (request.args.get("busca", "") or "").strip().lower()

    # ✅ filtro opcional categoria
    categoria_raw = (request.args.get("categoria", "") or "").strip()
    categoria_sel = int(categoria_raw) if categoria_raw.isdigit() else None

    # ✅ visualizar pagos
    mostrar_pagos = request.args.get("pagos", "") == "1"

    # ✅ filtros avançados
    filtro_tipo = request.args.get("filtro_tipo", "")
    if filtro_tipo not in ['entrada', 'saida']:
        filtro_tipo = None

    # Categorias incluir (múltipla seleção)
    categorias_incluir_raw = request.args.get("cat_incluir", "")
    categorias_incluir = [int(x) for x in categorias_incluir_raw.split(',') if x.isdigit()] if categorias_incluir_raw else None

    # Categorias excluir (múltipla seleção)
    categorias_excluir_raw = request.args.get("cat_excluir", "")
    categorias_excluir = [int(x) for x in categorias_excluir_raw.split(',') if x.isdigit()] if categorias_excluir_raw else None

    # ✅ ordenação
    ordenar_por = request.args.get("ordenar", "data")
    ordem = request.args.get("ordem", "desc")
    
    # Validar parâmetros
    if ordenar_por not in ['data', 'descricao', 'categoria', 'valor_total', 'parcelas']:
        ordenar_por = "data"
    if ordem not in ['asc', 'desc']:
        ordem = "desc"

    # ✅ paginação
    try:
        pagina = int(request.args.get("pagina", 1))
    except ValueError:
        pagina = 1
    if pagina < 1:
        pagina = 1

    # POST: criar transação
    if request.method == "POST":
        descricao = (request.form.get("descricao") or "").strip()
        valor_str = (request.form.get("valor") or "").strip()
        tipo = (request.form.get("tipo") or "").strip()
        data_str = (request.form.get("data") or "").strip()
        parcelas_str = (request.form.get("parcelas") or "").strip()

        # ✅ categoria no form (opcional)
        cat_form = (request.form.get("categoria_id") or "").strip()
        categoria_id = int(cat_form) if cat_form.isdigit() else None

        observacoes = (request.form.get("observacoes") or "").strip()
        recorrente = request.form.get("recorrente") == "on"
        tipo_entrada = request.form.get("tipo_entrada") or None  # salario, entrada_manual, ou None

        if not descricao:
            flash("Informe uma descrição.", "error")
            return redirect(url_for("home", mes=mes_sel, ano=ano_sel, categoria=categoria_raw, busca=busca))

        if not valor_str:
            flash("Informe um valor.", "error")
            return redirect(url_for("home", mes=mes_sel, ano=ano_sel, categoria=categoria_raw, busca=busca))

        if tipo not in ("entrada", "saida"):
            flash("Selecione o tipo (Entrada ou Saída).", "error")
            return redirect(url_for("home", mes=mes_sel, ano=ano_sel, categoria=categoria_raw, busca=busca))

        try:
            valor_total = float(valor_str)
        except ValueError:
            flash("Valor inválido.", "error")
            return redirect(url_for("home", mes=mes_sel, ano=ano_sel, categoria=categoria_raw, busca=busca))

        if tipo == "saida":
            valor_total = -abs(valor_total)
        else:
            valor_total = abs(valor_total)

        try:
            data_compra = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else hoje
        except ValueError:
            data_compra = hoje

        try:
            parcelas = int(parcelas_str) if parcelas_str else 1
        except ValueError:
            parcelas = 1
        if parcelas <= 0:
            parcelas = 1

        valor_parcela = valor_total / parcelas

        # Se for recorrente, ignora parcelas e define como 999 (infinito)
        if recorrente:
            parcelas = 999
            valor_parcela = valor_total

        t = Transacao(
            user_id=current_user.id,
            categoria_id=categoria_id,
            descricao=descricao,
            valor_total=valor_total,
            tipo=tipo,
            data=data_compra,
            parcelas=parcelas,
            valor_parcela=valor_parcela,
            observacoes=observacoes if observacoes else None,
            recorrente=recorrente,
            tipo_entrada=tipo_entrada,
        )
        db.session.add(t)
        db.session.commit()

        flash("Transação salva ✅", "ok")
        return redirect(url_for("home", mes=mes_sel, ano=ano_sel, categoria=categoria_raw, busca=busca))

    # GET: listar
    transacoes_todas = obter_transacoes_do_usuario(
        current_user.id, busca, mostrar_pagos, 
        filtro_tipo, categorias_incluir, categorias_excluir,
        ordenar_por, ordem
    )
    categorias = listar_categorias(current_user.id)

    # Listar salários (separado)
    salarios = Transacao.query.filter_by(
        user_id=current_user.id, 
        tipo_entrada="salario"
    ).order_by(Transacao.descricao.asc()).all()

    # Listar entradas manuais (apenas as do tipo entrada_manual)
    entradas_manuais = Transacao.query.filter(
        Transacao.user_id == current_user.id,
        Transacao.tipo_entrada == "entrada_manual"
    ).order_by(Transacao.data.desc()).limit(10).all()

    # Paginação
    itens_por_pagina = 25
    total_itens = len(transacoes_todas)
    total_paginas = (total_itens + itens_por_pagina - 1) // itens_por_pagina
    if pagina > total_paginas and total_paginas > 0:
        pagina = total_paginas

    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina
    transacoes = transacoes_todas[inicio:fim]

    anos_existentes = [t["data"].year for t in transacoes] or [hoje.year]
    ano_min = min(anos_existentes + [hoje.year]) - 1
    ano_max = max(anos_existentes + [hoje.year]) + 1
    anos_dropdown = list(range(ano_min, ano_max + 1))
    meses_dropdown = list(range(1, 13))

    # Calcular resumo com TODAS as transações (não paginadas)
    total_entradas, total_saidas_normal, saldo = calcular_resumo_mes(transacoes_todas, ano_sel, mes_sel)
    total_saidas_categoria = calcular_saidas_categoria_mes(transacoes_todas, ano_sel, mes_sel, categoria_sel)

    # ✅ card vermelho mostra categoria se selecionada, senão normal
    total_saidas = total_saidas_categoria if categoria_sel is not None else total_saidas_normal

    # Gráfico com TODAS as transações
    graf_labels, graf_entradas, graf_despesas = calcular_grafico(transacoes_todas, ano_sel, mes_sel)

    return render_template(
        "index.html",
        transacoes=transacoes,
        categorias=categorias,
        categoria_sel=categoria_sel,

        busca=busca,
        mes_sel=mes_sel,
        ano_sel=ano_sel,
        meses_dropdown=meses_dropdown,
        anos_dropdown=anos_dropdown,

        total_entradas=total_entradas,
        total_saidas=total_saidas,
        saldo=saldo,

        graf_labels=graf_labels,
        graf_entradas=graf_entradas,
        graf_despesas=graf_despesas,

        mostrar_pagos=mostrar_pagos,
        pagina=pagina,
        total_paginas=total_paginas,

        filtro_tipo=filtro_tipo,
        categorias_incluir=categorias_incluir or [],
        categorias_excluir=categorias_excluir or [],

        ordenar_por=ordenar_por,
        ordem=ordem,

        salarios=salarios,
        entradas_manuais=entradas_manuais,
    )


@app.route("/remover/<int:item_id>", methods=["POST"])
@login_required
def remover(item_id):
    t = Transacao.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not t:
        flash("Não encontrei essa transação (ou não é sua).", "error")
    else:
        db.session.delete(t)
        db.session.commit()
        flash("Transação removida ✅", "ok")

    mes = request.args.get("mes", "")
    ano = request.args.get("ano", "")
    busca = request.args.get("busca", "")
    categoria = request.args.get("categoria", "")
    return redirect(url_for("home", mes=mes, ano=ano, categoria=categoria, busca=busca))


@app.route("/editar/<int:item_id>", methods=["POST"])
@login_required
def editar(item_id):
    t = Transacao.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not t:
        flash("Não encontrei essa transação (ou não é sua).", "error")
        return redirect(url_for("home"))

    mes_sel = request.args.get("mes", "")
    ano_sel = request.args.get("ano", "")
    busca = request.args.get("busca", "")
    categoria = request.args.get("categoria", "")

    descricao = (request.form.get("descricao") or "").strip()
    valor_str = (request.form.get("valor") or "").strip()
    tipo = (request.form.get("tipo") or "").strip()
    data_str = (request.form.get("data") or "").strip()
    parcelas_str = (request.form.get("parcelas") or "").strip()

    # ✅ categoria no edit (opcional)
    cat_form = (request.form.get("categoria_id") or "").strip()
    categoria_id = int(cat_form) if cat_form.isdigit() else None

    observacoes = (request.form.get("observacoes") or "").strip()
    recorrente = request.form.get("recorrente") == "on"

    if not descricao:
        flash("Informe uma descrição.", "error")
        return redirect(url_for("home", mes=mes_sel, ano=ano_sel, categoria=categoria, busca=busca))

    try:
        valor_total = float(valor_str)
    except ValueError:
        flash("Valor inválido.", "error")
        return redirect(url_for("home", mes=mes_sel, ano=ano_sel, categoria=categoria, busca=busca))

    if tipo not in ("entrada", "saida"):
        flash("Selecione o tipo (Entrada ou Saída).", "error")
        return redirect(url_for("home", mes=mes_sel, ano=ano_sel, categoria=categoria, busca=busca))

    if tipo == "saida":
        valor_total = -abs(valor_total)
    else:
        valor_total = abs(valor_total)

    try:
        data_compra = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        data_compra = datetime.today().date()

    try:
        parcelas = int(parcelas_str) if parcelas_str else 1
    except ValueError:
        parcelas = 1
    if parcelas <= 0:
        parcelas = 1

    # Se for recorrente, ajusta parcelas
    if recorrente:
        parcelas = 999
        valor_parcela = valor_total
    else:
        valor_parcela = valor_total / parcelas

    t.descricao = descricao
    t.valor_total = valor_total
    t.tipo = tipo
    t.data = data_compra
    t.parcelas = parcelas
    t.valor_parcela = valor_parcela
    t.categoria_id = categoria_id
    t.observacoes = observacoes if observacoes else None
    t.recorrente = recorrente

    db.session.commit()
    flash("Transação atualizada ✅", "ok")

    return redirect(url_for("home", mes=mes_sel, ano=ano_sel, categoria=categoria, busca=busca))


@app.route("/salarios", methods=["POST"])
@login_required
def cadastrar_salario():
    descricao = (request.form.get("descricao") or "").strip()
    valor_str = (request.form.get("valor") or "").strip()
    dia_pagamento = request.form.get("dia_pagamento") or "5"

    if not descricao:
        flash("Informe uma descrição para o salário.", "error")
        return redirect(url_for("home"))

    if not valor_str:
        flash("Informe o valor do salário.", "error")
        return redirect(url_for("home"))

    try:
        valor = float(valor_str)
    except ValueError:
        flash("Valor inválido.", "error")
        return redirect(url_for("home"))

    try:
        dia = int(dia_pagamento)
        if dia < 1 or dia > 28:
            dia = 5
    except ValueError:
        dia = 5

    # Data de início: primeiro salário do mês atual ou próximo
    hoje = datetime.today().date()
    if hoje.day <= dia:
        data_inicio = date(hoje.year, hoje.month, dia)
    else:
        # Próximo mês
        if hoje.month == 12:
            data_inicio = date(hoje.year + 1, 1, dia)
        else:
            data_inicio = date(hoje.year, hoje.month + 1, dia)

    t = Transacao(
        user_id=current_user.id,
        descricao=descricao,
        valor_total=valor,
        tipo="entrada",
        data=data_inicio,
        parcelas=999,  # Infinito
        valor_parcela=valor,
        recorrente=True,
        tipo_entrada="salario",
    )
    db.session.add(t)
    db.session.commit()

    flash("Salário cadastrado com sucesso ✅", "ok")
    return redirect(url_for("home"))


@app.route("/salarios/<int:item_id>/excluir", methods=["POST"])
@login_required
def excluir_salario(item_id):
    t = Transacao.query.filter_by(id=item_id, user_id=current_user.id, tipo_entrada="salario").first()
    if not t:
        flash("Salário não encontrado.", "error")
    else:
        db.session.delete(t)
        db.session.commit()
        flash("Salário excluído ✅", "ok")

    return redirect(url_for("home"))


@app.route("/marcar_pago/<int:item_id>", methods=["POST"])
@login_required
def marcar_pago(item_id):
    t = Transacao.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not t:
        flash("Não encontrei essa transação (ou não é sua).", "error")
    else:
        t.pago = True
        db.session.commit()
        flash("Transação marcada como paga ✅", "ok")

    mes = request.args.get("mes", "")
    ano = request.args.get("ano", "")
    busca = request.args.get("busca", "")
    categoria = request.args.get("categoria", "")
    return redirect(url_for("home", mes=mes, ano=ano, categoria=categoria, busca=busca))


# ---------------- "Migração" simples para SQLite ----------------
def ensure_sqlite_schema():
    """
    SQLite não altera tabela automaticamente no create_all.
    Isso tenta adicionar colunas se o banco já existia.
    """
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if not uri.startswith("sqlite:"):
        return

    # cria tabelas novas
    db.create_all()

    # verifica colunas de transacoes
    cols_transacoes = db.session.execute(text("PRAGMA table_info(transacoes)")).fetchall()
    col_names_transacoes = {c[1] for c in cols_transacoes}

    if "categoria_id" not in col_names_transacoes:
        db.session.execute(text("ALTER TABLE transacoes ADD COLUMN categoria_id INTEGER"))
        db.session.commit()

    if "observacoes" not in col_names_transacoes:
        db.session.execute(text("ALTER TABLE transacoes ADD COLUMN observacoes TEXT"))
        db.session.commit()

    if "pago" not in col_names_transacoes:
        db.session.execute(text("ALTER TABLE transacoes ADD COLUMN pago BOOLEAN DEFAULT 0"))
        db.session.commit()

    if "recorrente" not in col_names_transacoes:
        db.session.execute(text("ALTER TABLE transacoes ADD COLUMN recorrente BOOLEAN DEFAULT 0"))
        db.session.commit()

    if "tipo_entrada" not in col_names_transacoes:
        db.session.execute(text("ALTER TABLE transacoes ADD COLUMN tipo_entrada VARCHAR(20)"))
        db.session.commit()

    # verifica colunas de users
    cols_users = db.session.execute(text("PRAGMA table_info(users)")).fetchall()
    col_names_users = {c[1] for c in cols_users}

    if "nome" not in col_names_users:
        db.session.execute(text("ALTER TABLE users ADD COLUMN nome VARCHAR(100) DEFAULT 'Usuário'"))
        db.session.commit()

    if "foto_perfil" not in col_names_users:
        db.session.execute(text("ALTER TABLE users ADD COLUMN foto_perfil VARCHAR(255)"))
        db.session.commit()


with app.app_context():
    ensure_sqlite_schema()


if __name__ == "__main__":
    app.run(debug=True)
