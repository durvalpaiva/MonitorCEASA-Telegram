import streamlit as st
import os
import glob
import pandas as pd
import pdfplumber
import requests
from bs4 import BeautifulSoup

def baixar_pdf_ceasa():
    url = 'https://transparencia.ceasa.rn.gov.br/cotacoes'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        st.error(f'Erro ao acessar página de cotações: {e}')
        return None
    soup = BeautifulSoup(response.text, 'html.parser')
    pdf_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/download/' in href:
            import re
            match = re.search(r'/download/(\d+)', href)
            if match:
                numero = int(match.group(1))
                pdf_links.append((numero, href))
    if not pdf_links:
        st.error('Nenhum PDF encontrado na página de cotações.')
        return None
    pdf_links.sort(reverse=True)
    _, pdf_link = pdf_links[0]
    # Se o link já é absoluto, use direto. Se for relativo, complete.
    if pdf_link.startswith('http'):
        pdf_url = pdf_link
    else:
        pdf_url = f'https://transparencia.ceasa.rn.gov.br{pdf_link}'
    st.info(f'Baixando PDF mais recente: {pdf_url}')
    try:
        pdf_response = requests.get(pdf_url, headers=headers, timeout=30)
        pdf_response.raise_for_status()
        with open('cotacao_ceasa.pdf', 'wb') as f:
            f.write(pdf_response.content)
        return 'cotacao_ceasa.pdf'
    except Exception as e:
        st.error(f'Erro ao baixar PDF: {e}')
        return None

def baixar_pdf_por_link(pdf_link):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    if not pdf_link.startswith('http'):
        pdf_link = 'https://transparencia.ceasa.rn.gov.br' + pdf_link
    try:
        pdf_response = requests.get(pdf_link, headers=headers, timeout=30)
        pdf_response.raise_for_status()
        with open('cotacao_ceasa.pdf', 'wb') as f:
            f.write(pdf_response.content)
        return 'cotacao_ceasa.pdf'
    except Exception as e:
        st.error(f'Erro ao baixar PDF: {e}')
        return None

def encontrar_ultimo_pdf():
    pdfs = glob.glob('*.pdf')
    if not pdfs:
        return None
    return max(pdfs, key=os.path.getctime)

def tratar_e_consolidar_pdf(pdf_path):
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
        return None
    df_final = pd.concat(dfs, ignore_index=True)
    # Extrair data do boletim
    import re
    data_boletim = None
    for idx, row in df_final.iterrows():
        # Tenta extrair da coluna Unidade
        match = re.search(r'(\d{2}/\d{2}/\d{4})', str(row.get('Unidade', '')))
        if not match:
            # Se não encontrar, tenta extrair da coluna Produto
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

def main():
    st.title('Monitoramento CEASA - Boletim consolidado')
    st.write('Este painel mostra os dados do boletim CEASA extraído do PDF, com tratamento e normalização.')
    st.info('Baixando e tratando o PDF mais recente do CEASA...')
    pdf_path = baixar_pdf_ceasa()
    if not pdf_path:
        st.error('Não foi possível baixar o PDF do CEASA.')
        return
    df = tratar_e_consolidar_pdf(pdf_path)
    if df is not None:
        produtos = df['Produto'].dropna().unique().tolist() if 'Produto' in df.columns else []
        produto_selecionado = st.selectbox('Filtrar por produto', ['Todos'] + produtos)
        if produto_selecionado != 'Todos':
            df = df[df['Produto'] == produto_selecionado]
        st.dataframe(df)
    else:
        st.error('Falha ao tratar PDF.')

if __name__ == '__main__':
    main()
