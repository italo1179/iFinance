"""
Script de migração única para manter entradas existentes como transações normais.
Execute uma vez: python migrar_entradas.py
"""

from app import app, db, Transacao

with app.app_context():
    # Buscar todas as entradas que não têm tipo_entrada definido
    entradas = Transacao.query.filter(
        Transacao.tipo == 'entrada',
        Transacao.tipo_entrada == None
    ).all()
    
    print(f"\n🔍 Encontradas {len(entradas)} entradas sem tipo_entrada")
    
    if entradas:
        print("\n📝 Entradas encontradas:")
        for e in entradas:
            print(f"  - ID {e.id}: {e.descricao} - R$ {e.valor_total:.2f}")
        
        resposta = input("\n❓ Deseja manter todas como transações normais (aparecerão na lista principal)? (s/n): ")
        
        if resposta.lower() == 's':
            # Não faz nada - tipo_entrada continua NULL, que é o comportamento correto
            # para aparecer na lista principal
            print("\n✅ Perfeito! As entradas já estão configuradas corretamente.")
            print("   Elas continuarão aparecendo na lista principal (tipo_entrada = NULL)")
        else:
            print("\n⚠️  Migração cancelada. Nenhuma alteração foi feita.")
    else:
        print("\n✅ Nenhuma entrada encontrada sem tipo_entrada. Tudo certo!")
    
    print("\n" + "="*70)
    print("📊 RESUMO DA CONFIGURAÇÃO ATUAL:")
    print("="*70)
    
    total = Transacao.query.count()
    salarios = Transacao.query.filter_by(tipo_entrada='salario').count()
    entradas_manuais = Transacao.query.filter_by(tipo_entrada='entrada_manual').count()
    transacoes_normais = Transacao.query.filter_by(tipo_entrada=None).count()
    
    print(f"📌 Total de transações: {total}")
    print(f"💵 Salários automáticos: {salarios}")
    print(f"✍️  Entradas manuais: {entradas_manuais}")
    print(f"📝 Transações normais: {transacoes_normais}")
    print("="*70)
