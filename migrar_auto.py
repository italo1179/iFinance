"""
Script de migração automática - mantém entradas existentes como transações normais
"""

from app import app, db, Transacao

with app.app_context():
    # Buscar todas as entradas sem tipo_entrada
    entradas = Transacao.query.filter(
        Transacao.tipo == 'entrada',
        Transacao.tipo_entrada == None
    ).all()
    
    print(f"\n✅ Encontradas {len(entradas)} entradas que já estão corretas!")
    print("   (tipo_entrada = NULL significa que aparecem na lista principal)")
    
    if entradas:
        print("\n📝 Entradas:")
        for e in entradas:
            print(f"  - {e.descricao}: R$ {e.valor_total:.2f} ({e.data.strftime('%d/%m/%Y')})")
    
    print("\n" + "="*70)
    print("📊 RESUMO:")
    print("="*70)
    
    total = Transacao.query.count()
    salarios = Transacao.query.filter_by(tipo_entrada='salario').count()
    entradas_manuais = Transacao.query.filter_by(tipo_entrada='entrada_manual').count()
    transacoes_normais = Transacao.query.filter_by(tipo_entrada=None).count()
    
    print(f"📌 Total: {total}")
    print(f"💵 Salários automáticos: {salarios}")
    print(f"✍️  Entradas manuais (modal): {entradas_manuais}")
    print(f"📝 Transações normais (lista principal): {transacoes_normais}")
    print("="*70)
    print("\n✅ Tudo configurado corretamente!")
