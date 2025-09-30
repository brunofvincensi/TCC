# -*- coding: utf-8 -*-
"""
Web Scraping InfoMoney - Coleta de notícias
-------------------------------------------
Fluxo:
1. Converte nome da empresa para URL do InfoMoney
2. Abre página "tudo-sobre" no Selenium
3. Clica em "Carregar mais" até encontrar notícia mais antiga que o limite
4. Extrai links + datas dos cards
5. Para cada link, coleta título, manchete, texto, data
6. Pré-processa textos (tokens, stems, lemmas)
7. Salva no banco usando news_service
"""

import time
import re
import string
from datetime import datetime, timedelta

import requests
import pandas as pd
from bs4 import BeautifulSoup

# --- Selenium ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# --- NLP ---
import spacy
import nltk
from nltk.corpus import stopwords
from nltk.stem import RSLPStemmer
from nltk.tokenize import word_tokenize

# --- Utils próprios ---
from utils import yahoo_finance
from utils.database import initialize_database
from utils.news_service import get_news_service

# ------------------- Configuração NLP -------------------

# Download de recursos NLTK (executa apenas uma vez)
nltk.download('rslp')
nltk.download('stopwords')
nltk.download('punkt')
nltk.download('punkt_tab')

# Carrega modelo SpaCy em português
try:
    nlp = spacy.load("pt_core_news_sm")
except OSError:
    print("⚠️ Modelo pt_core_news_sm não encontrado. Execute: python -m spacy download pt_core_news_sm")
    nlp = None

# Stopwords e Stemmer
stop_words = set(stopwords.words('portuguese'))
stemmer = RSLPStemmer()

# ------------------- Funções Utilitárias -------------------

def converter_nome_empresa_para_url(nome_empresa: str) -> str:
    """
    Converte nome da empresa no formato usado pelo InfoMoney.
    Ex.: 'Banco do Brasil' -> 'banco-do-brasil'
    """
    nome_lower = nome_empresa.lower()
    nome_limpo = re.sub(r'[àáâãäå]', 'a', nome_lower)
    nome_limpo = re.sub(r'[èéêë]', 'e', nome_limpo)
    nome_limpo = re.sub(r'[ìíîï]', 'i', nome_limpo)
    nome_limpo = re.sub(r'[òóôõö]', 'o', nome_limpo)
    nome_limpo = re.sub(r'[ùúûü]', 'u', nome_limpo)
    nome_limpo = re.sub(r'[ç]', 'c', nome_limpo)
    nome_url = re.sub(r'\s+', '-', nome_limpo)       # espaços -> hífen
    nome_url = re.sub(r'[^a-z0-9\-]', '', nome_url)  # remove caracteres especiais
    return nome_url

def texto_relativo_para_data_simples(texto: str):
    """
    Converte '... 5 dias atrás' ou '... 12 horas atrás' em datetime.
    Procura o número imediatamente antes de 'atrás'.
    """
    if not texto:
        return None

    agora = datetime.now()
    s = texto.lower()

    m = re.search(r'(\d+)\s*(horas?|dias?|semanas?|meses?)\s+atrás', s)
    if not m:
        return agora  # fallback

    quantidade = int(m.group(1))
    unidade = m.group(2)

    if 'hora' in unidade:
        delta = timedelta(hours=quantidade)
    elif 'dia' in unidade:
        delta = timedelta(days=quantidade)
    elif 'semana' in unidade:
        delta = timedelta(weeks=quantidade)
    elif 'mes' in unidade:
        delta = timedelta(days=30 * quantidade)
    else:
        delta = timedelta(days=quantidade)

    return agora - delta

def coletar_links_e_datas(soup: BeautifulSoup):
    """
    Coleta os links e datas (convertidas) dos cards de notícias.
    """
    cards = soup.find_all("div", {"data-ds-component": "card-sm"})
    lista = []

    for card in cards:
        a = card.find("a", href=True)
        if not a:
            continue

        # Busca div com 'atrás'
        tempo_texto = ""
        for d in card.find_all("div", class_="inline-flex"):
            t = d.get_text(strip=True).lower()
            if "atrás" in t:
                tempo_texto = t
                break

        data_pub = texto_relativo_para_data_simples(tempo_texto)
        lista.append({"link": a['href'], "data": data_pub})

    return lista

def processar(texto: str):
    """
    Pré-processamento para NLP:
    - minúsculas
    - remove pontuação e caracteres especiais
    - tokenização
    - remove stopwords
    - stemming
    - lematização (se SpaCy disponível)
    """
    texto = texto.lower()
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    texto = re.sub(r'[^a-záéíóúâêîôûãõç ]', ' ', texto)

    tokens = word_tokenize(texto, language='portuguese')
    tokens = [t for t in tokens if t not in stop_words and len(t) > 2]
    stems = [stemmer.stem(t) for t in tokens]

    if nlp:
        doc = nlp(" ".join(tokens))
        lemmas = [token.lemma_ for token in doc]
    else:
        lemmas = stems  # fallback

    return {"tokens": tokens, "stems": stems, "lemmas": lemmas}

def get_article_content(url: str):
    """
    Extrai título, manchete, data e corpo do artigo do InfoMoney.
    """
    r = requests.get(url)
    sp = BeautifulSoup(r.text, "html.parser")

    titulo_tag = sp.find("div", {"data-ds-component": "article-title"})
    titulo = titulo_tag.find("h1").get_text(strip=True) if titulo_tag else ""

    manchete_tag = titulo_tag.find("div") if titulo_tag else None
    manchete = manchete_tag.get_text(strip=True) if manchete_tag else ""

    article_tag = sp.find("article", {"data-ds-component": "article"})
    paragrafos = article_tag.find_all("p") if article_tag else []
    texto = " ".join([p.get_text(strip=True) for p in paragrafos])

    data_tag = sp.find("time")
    data_pub_str = data_tag.get_text(strip=True) if data_tag else "Sem data"
    data_pub = datetime.strptime(data_pub_str, "%d/%m/%Y %Hh%M")

    return {"titulo": titulo, "manchete": manchete, "data": data_pub, "texto": texto, "link": url}

def save(df_tokens: pd.DataFrame, news_service, ticker_id: int):
    """
    Salva as notícias processadas no banco via serviço.
    Processa título, manchete e corpo com NLP antes de salvar.
    """
    if not news_service:
        return

    print("💾 Salvando dados no banco de dados...")
    saved_count = 0

    for _, row in df_tokens.iterrows():
        try:
            news_data = {
                'url': row['link'],
                'data_publicacao': row['data'],
                'autor': None,
                'fonte': 'InfoMoney',
                'tipo_fonte': 'INFO_MONEY',
                'categoria': None,
                'sentimento': None,
                'relevancia': 0.0
            }

            # Pré-processamento
            titulo_processed = processar(row['titulo'])
            manchete_processed = processar(row['manchete'])
            corpo_processed = processar(row['texto'])

            text_processing_data = {
                'titulo': {
                    'texto_bruto': row['titulo'],
                    'tokens_normalizados': ' '.join(titulo_processed['tokens']),
                    'tokens_stemming': ' '.join(titulo_processed['stems']),
                    'tokens_lemma': ' '.join(titulo_processed['lemmas']),
                },
                'manchete': {
                    'texto_bruto': row['manchete'],
                    'tokens_normalizados': ' '.join(manchete_processed['tokens']),
                    'tokens_stemming': ' '.join(manchete_processed['stems']),
                    'tokens_lemma': ' '.join(manchete_processed['lemmas']),
                },
                'corpo': {
                    'texto_bruto': row['texto'],
                    'tokens_normalizados': ' '.join(corpo_processed['tokens']),
                    'tokens_stemming': ' '.join(corpo_processed['stems']),
                    'tokens_lemma': ' '.join(corpo_processed['lemmas']),
                }
            }

            ticker_id, news_id, processing_ids = news_service.save_complete_news_data_with_ticker_id(
                ticker_id=ticker_id,
                news_data=news_data,
                text_processing_data=text_processing_data
            )

            if ticker_id and news_id and any(processing_ids):
                saved_count += 1

        except Exception as e:
            print(f"Erro ao salvar notícia: {e}")
            continue

    print(f"✅ {saved_count} notícias salvas no banco de dados")

# ------------------- Função Principal -------------------

def web_scrapping(trading_mode, ticker, ticker_id, company_name, news_service=None):
    """
    Fluxo principal:
    - Converte nome para URL
    - Abre página InfoMoney
    - Carrega mais enquanto notícias dentro do limite
    - Extrai dados de cada artigo
    - Salva no banco
    """
    name_to_url = converter_nome_empresa_para_url(company_name)
    base_url = f"https://www.infomoney.com.br/tudo-sobre/{name_to_url}"
    limite = datetime.now() - timedelta(days=7)

    driver = webdriver.Chrome()
    driver.get(base_url)
    wait = WebDriverWait(driver, 10)

    todos_links = []
    while True:
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Coleta links + datas atuais
        todos_links = coletar_links_e_datas(soup)

        # Verifica se existe alguma notícia mais antiga que o limite
        mais_antiga = min([item["data"] for item in todos_links])
        if mais_antiga < limite:
            print("⛔ Encontrada notícia mais antiga que o limite, parando...")
            break

        # Tenta clicar em "Carregar mais"
        try:
            botao = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Carregar mais')]")))
            driver.execute_script("arguments[0].scrollIntoView(true);", botao)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", botao)
        except TimeoutException:
            print("⛔ Não há mais botão 'Carregar mais'.")
            break

    driver.quit()

    dentro_limite = [item for item in todos_links if item["data"] >= limite]

    dados = []
    for d in dentro_limite:
        try:
            content = get_article_content(d["link"])
            dados.append(content)
        except Exception as e:
            print("Erro no link", d["link"], e)

    df = pd.DataFrame(dados)
    print(df.head())

    save(df, news_service, ticker_id)

# ------------------- Execução Direta -------------------

if __name__ == "__main__":
    news_service = get_news_service()
    if not initialize_database():
        print("❌ Falha ao inicializar banco. Verifique conexão MySQL.")
    else:
        ticker_id, company_name = yahoo_finance.get_ativo("VALE3", get_news_service())
        web_scrapping("BUY_&_HOLD", "VALE3", ticker_id, company_name, news_service)
