import os
import requests
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from send import send_telegram_message
import pdfplumber

load_dotenv()
token = os.getenv('TELEGRAM_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')
"""
Script para filtrar produtos do boletim CEASA e enviar resumo para o Telegram.
Requer: cotacao_ceasa.pdf gerado pelo main.py, .env com TELEGRAM_TOKEN e TELEGRAM_CHAT_ID, send.py
"""
import os
import pandas as pd
import pdfplumber
from dotenv import load_dotenv
from send import send_telegram_message

load_dotenv()
token = os.getenv('TELEGRAM_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

def tratar_e_consolidar_pdf(pdf_path):
    """Extrai e consolida tabelas do PDF conforme lógica do main.py"""
    import re
    dfs = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue
            colunas = table[0]
            colunas_padrao = ['Produto', 'Unidade', 'Origem', 'Preço Mínimo', 'Preço Comum', 'Preço Máximo', 'Preço Kg', 'Situação Mercado']
            if len(colunas) >= 8:
                colunas = colunas[-8:]
            df_page = pd.DataFrame(table[1:], columns=colunas)
            if set(colunas_padrao).issubset(df_page.columns):
                df_page = df_page[colunas_padrao]
            else:
                df_page.columns = colunas_padrao
            df_page = df_page.dropna(how='all')
            df_page = df_page[df_page['Produto'].notnull()]
            df_page = df_page[df_page['Produto'].astype(str).str.strip() != '']
            dfs.append(df_page)
    if not dfs:
        return None
    df_final = pd.concat(dfs, ignore_index=True)
    # Extrai data do boletim
    data_boletim = None
    for idx, row in df_final.iterrows():
        match = re.search(r'(\d{2}/\d{2}/\d{4})', str(row.get('Unidade', '')))
        if not match:
            match = re.search(r'(\d{2}/\d{2}/\d{4})', str(row.get('Produto', '')))
        if match:
            data_boletim = match.group(1)
            break
    df_final['Data'] = data_boletim
    return df_final

def main():
    pdf_path = 'cotacao_ceasa.pdf'
    if not os.path.exists(pdf_path):
        send_telegram_message(token, chat_id, 'Arquivo cotacao_ceasa.pdf não encontrado. Execute o main.py primeiro.')
        print('Arquivo cotacao_ceasa.pdf não encontrado. Mensagem enviada ao Telegram.')
        return
    df = tratar_e_consolidar_pdf(pdf_path)
    if df is None:
        send_telegram_message(token, chat_id, 'Erro ao tratar cotacao_ceasa.pdf. Não foi possível enviar os preços.')
        print('Erro ao tratar PDF. Mensagem enviada ao Telegram.')
        return
    # Filtra produtos contendo "alface" no nome
    filtro = df['Produto'].str.lower().str.contains('alface')
    alface_df = df[filtro]
    if alface_df.empty:
        mensagem = 'Nenhum produto contendo "alface" encontrado no boletim.'
    else:
        mensagem = 'Produtos contendo "alface":\n\n'
        for idx, row in alface_df.iterrows():
            # Formata cada linha como texto
            linha = '\n'.join([f'{col}: {row[col]}' for col in alface_df.columns])
            mensagem += linha + '\n\n'
    send_telegram_message(token, chat_id, mensagem)
    print('Mensagem enviada para o Telegram!')

if __name__ == '__main__':
    main()
load_dotenv()

# URL do site CEASA
CEASA_URL = 'https://www.ceasa.pr.gov.br/Pagina/Boletins-diarios'

# Produtos de interesse
PRODUTOS = [
    'alface', 'rucula', 'coentro', 'cebolinha', 'coco verde', 'coco seco', 'couve flor', 'abacate',
    'farinha de mand. fina', 'farinha de mand. media', 'batata doce'
]

# Função para baixar o PDF mais recente
def baixar_pdf_ceasa():
    try:
        response = requests.get(CEASA_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        link = None
        for a in soup.find_all('a', href=True):
            if a['href'].endswith('.pdf'):
                link = a['href']
                break
        if not link:
            raise Exception('PDF não encontrado no site CEASA.')
        if not link.startswith('http'):
            link = 'https://www.ceasa.pr.gov.br' + link
        pdf_path = 'boletim_ceasa.pdf'
        r = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        with open(pdf_path, 'wb') as f:
            f.write(r.content)
        return pdf_path
    except Exception as e:
        print(f'Erro ao baixar PDF: {e}')
        # Tentar fallback usando main.py
        try:
            import main
            if hasattr(main, 'baixar_pdf_ceasa'):
                print('Tentando baixar PDF usando método do main.py...')
                pdf_path = main.baixar_pdf_ceasa()
                if pdf_path:
                    return pdf_path
        except Exception as e2:
            print(f'Fallback main.py falhou: {e2}')
        return None

# Função para extrair tabela do PDF


def buscar_info(df, produto):
    try:
        filtro = df['Produto'].str.lower().str.contains(produto)
        resultado = df[filtro]
        if resultado.empty:
            return f"{produto.title()}: Informação não disponível."
        resultado = resultado.sort_values('Médio', ascending=False).iloc[0]
        nome = resultado.get('Produto', produto.title())
        unidade = resultado.get('Unidade', 'N/A')
        minimo = resultado.get('Mínimo', 'N/A')
        medio = resultado.get('Médio', 'N/A')
        maximo = resultado.get('Máximo', 'N/A')
        situacao = resultado.get('Sit.Mercado', resultado.get('Situação', 'N/A'))
        # Limpar possíveis caracteres estranhos
        def clean(val):
            return str(val).replace('\r', '').replace('\n', '').replace('  ', ' ').strip()
        return (f"{clean(nome)} ({clean(unidade)}):\n"
                f"  Mínimo: {clean(minimo)}\n"
                f"  Médio: {clean(medio)}\n"
                f"  Máximo: {clean(maximo)}\n"
                f"  Situação de Mercado: {clean(situacao)}\n")
    except Exception as e:
        return f"{produto.title()}: Erro ao buscar informação."
import re

def tratar_e_consolidar_pdf(pdf_path):
    print(f"[DEBUG] PDF path: {pdf_path}")
    dfs = []
    with pdfplumber.open(pdf_path) as pdf:
        print(f"[DEBUG] Número de páginas no PDF: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages):
            table = page.extract_table()
            print(f"[DEBUG] Página {i+1}: Tabela extraída? {'Sim' if table else 'Não'}")
            if not table:
                continue
            colunas = table[0]
            print(f"[DEBUG] Colunas encontradas: {colunas}")
            colunas_padrao = ['Produto', 'Unidade', 'Origem', 'Preço Mínimo', 'Preço Comum', 'Preço Máximo', 'Preço Kg', 'Situação Mercado']
            if len(colunas) >= 8:
                colunas = colunas[-8:]
            df_page = pd.DataFrame(table[1:], columns=colunas)
            # Padronizar colunas
            if set(colunas_padrao).issubset(df_page.columns):
                df_page = df_page[colunas_padrao]
            else:
                df_page.columns = colunas_padrao
            # Remove linhas totalmente vazias
            df_page = df_page.dropna(how='all')
            # Remove linhas onde 'Produto' está vazio ou não é texto
            df_page = df_page[df_page['Produto'].notnull()]
            df_page = df_page[df_page['Produto'].astype(str).str.strip() != '']
            dfs.append(df_page)
    if not dfs:
        print("[DEBUG] Nenhuma tabela válida encontrada no PDF.")
        return None
    df_final = pd.concat(dfs, ignore_index=True)
    print(f"[DEBUG] DataFrame final gerado com {len(df_final)} linhas.")
    # Extrair data do boletim
    data_boletim = None
    for idx, row in df_final.iterrows():
        match = re.search(r'(\d{2}/\d{2}/\d{4})', str(row.get('Unidade', '')))
        if not match:
            match = re.search(r'(\d{2}/\d{2}/\d{4})', str(row.get('Produto', '')))
        if match:
            data_boletim = match.group(1)
            break
    # Remover linhas desalinhadas e inválidas
    df_final = df_final[df_final['Produto'].notnull()]
    df_final = df_final[df_final['Produto'].astype(str).str.strip() != '']
    df_final = df_final[~df_final['Produto'].astype(str).str.startswith('R$')]
    # Funções de normalização
    def extrair_kg(unidade):
        match = re.search(r'(\d+[\.,]?\d*)KG', unidade.upper())
        if match:
            return float(match.group(1).replace(',', '.'))
        return None
    def tratar_preco(valor):
        if pd.isnull(valor):
            return None
        valor = str(valor)
        valor = valor.replace('R$', '').replace(',', '.').replace(' ', '').strip()
        try:
            return float(valor)
        except:
            return None
    def preco_tratado(row, col):
        unidade = str(row['Unidade']).upper()
        preco = tratar_preco(row[col])
        if preco is None:
            return {'por_kg': None, 'por_unidade': None}
        if unidade == 'KG':
            return {'por_kg': preco, 'por_unidade': None}
        elif unidade == 'CEM':
            return {'por_kg': None, 'por_unidade': preco / 100}
        elif 'BAND.30UND' in unidade:
            return {'por_kg': None, 'por_unidade': preco / 30}
        elif 'KG' in unidade:
            kg = extrair_kg(unidade)
            if kg:
                return {'por_kg': preco / kg, 'por_unidade': None}
            else:
                return {'por_kg': None, 'por_unidade': preco}
        return {'por_kg': None, 'por_unidade': preco}
    for col in ['Preço Mínimo', 'Preço Comum', 'Preço Máximo']:
        df_final[col + ' por KG'] = df_final.apply(lambda row: preco_tratado(row, col)['por_kg'], axis=1)
        df_final[col + ' por Unidade'] = df_final.apply(lambda row: preco_tratado(row, col)['por_unidade'], axis=1)
    df_final['Data'] = data_boletim
    return df_final

# Função para buscar preços dos produtos
def buscar_info(df, produto):
    try:
        filtro = df['Produto'].str.lower().str.contains(produto)
        resultado = df[filtro]
        if resultado.empty:
            return f"{produto.title()}: Informação não disponível."
        resultado = resultado.sort_values('Médio', ascending=False).iloc[0]
        nome = resultado.get('Produto', produto.title())
        unidade = resultado.get('Unidade', 'N/A')
        minimo = resultado.get('Mínimo', 'N/A')
        medio = resultado.get('Médio', 'N/A')
        maximo = resultado.get('Máximo', 'N/A')
        situacao = resultado.get('Sit.Mercado', resultado.get('Situação', 'N/A'))
        # Limpar possíveis caracteres estranhos
        def clean(val):
            return str(val).replace('\r', '').replace('\n', '').replace('  ', ' ').strip()
        return (f"{clean(nome)} ({clean(unidade)}):\n"
                f"  Mínimo: {clean(minimo)}\n"
                f"  Médio: {clean(medio)}\n"
                f"  Máximo: {clean(maximo)}\n"
                f"  Situação de Mercado: {clean(situacao)}\n")
    except Exception as e:
        return f"{produto.title()}: Erro ao buscar informação."

def main():
    pdf_path = 'cotacao_ceasa.pdf'
    if not os.path.exists(pdf_path):
        send_telegram_message(token, chat_id, 'Arquivo cotacao_ceasa.pdf não encontrado. Execute o main.py primeiro.')
        print('Arquivo cotacao_ceasa.pdf não encontrado. Mensagem enviada ao Telegram.')
        return
    df = tratar_e_consolidar_pdf(pdf_path)
    if df is None:
        send_telegram_message(token, chat_id, 'Erro ao tratar cotacao_ceasa.pdf. Não foi possível enviar os preços.')
        print('Erro ao tratar PDF. Mensagem enviada ao Telegram.')
        return
    # Filtrar linhas onde o nome do produto contém "alface"
    filtro = df['Produto'].str.lower().str.contains('alface')
    alface_df = df[filtro]
    if alface_df.empty:
        mensagem = 'Nenhum produto contendo "alface" encontrado no boletim.'
    else:
        mensagem = 'Produtos contendo "alface":\n\n'
        for idx, row in alface_df.iterrows():
            mensagem += str(row) + '\n\n'
    send_telegram_message(token, chat_id, mensagem)
    print('Mensagem enviada para o Telegram!')

if __name__ == '__main__':
    main()
