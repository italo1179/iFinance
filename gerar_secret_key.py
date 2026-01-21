"""
Script para gerar SECRET_KEY para o Railway
Execute: python gerar_secret_key.py
"""

import secrets

secret_key = secrets.token_hex(32)

print("\n" + "="*70)
print("🔐 SECRET_KEY gerada com sucesso!")
print("="*70)
print(f"\n{secret_key}\n")
print("="*70)
print("\n📋 Copie e cole no Railway:")
print("   Variables → SECRET_KEY → Cole o valor acima")
print("="*70)
