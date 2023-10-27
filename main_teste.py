import json
import os
from datetime import datetime
from tempfile import NamedTemporaryFile

import pdfkit
import pendulum
import requests
from parsel import Selector

from src.searchers import DOUSearcher

dou = DOUSearcher()
busca = dou.exec_search(term_list=['ENAP'], dou_sections= ['TODOS'], search_date='DIA', field='TUDO', is_exact_search= True,
                            ignore_signature_match= True, force_rematch= False, reference_date= datetime(2020, 8, 20))
# print(busca)

# current_directory = os.path.dirname(__file__)
# parent_directory = os.path.dirname(current_directory)
# file_path_template_email = os.path.join(current_directory, 'src', 'template_email.html')
# file_path_template_item_email = os.path.join(current_directory, 'src', 'template_item_email.html')
#
# conteudo = ''
# with open(file_path_template_email, 'r') as template:
#     conteudo = f'{template.read()}'
#
# item_str = ''
# with open(file_path_template_item_email, 'r') as item_template:
#     item_str = item_template.read()
#
# texto = ''
# for group, results in busca.items():
#     for term, items in results.items():
#         for item in items:
#             dou._clean_html(item['abstract'])
#             texto += ((item_str.replace('{{link}}', item['href']).replace('{{section}}', item['section'])
#                        .replace('{{date}}', item['date'])).replace("{{title}}", item['title'])
#                       .replace("{{abstract}}", item['abstract']))
#
#
# pendulum.set_locale('pt_br')
# conteudo = conteudo.replace('{{conteudo}}', texto)
# conteudo = conteudo.replace('{{dia}}', pendulum.now().strftime('%d de %B de %Y'))
#
# print(conteudo)
#
#
# data_search = '23/10/2023'
#
# data = {'acao': 'publicacao_pesquisar',
#     'acao_origem': 'publicacao_pesquisar',
#     'id_orgao_publicacao': 0,
#     'rdo_data_publicacao': 'E',
#     'dta_inicio': data_search,
#     'dta_fim': data_search
# }
# r = requests.post('https://sei.enap.gov.br/sei/publicacoes/controlador_publicacoes.php',
#               params=data)
#
# selector = Selector(text=r.text)
#
#
# # editais = tree.xpath("(//td[@colspan='9'])/text()")
# result = []
# lista_resultados = selector.xpath("//tr[contains(@id,'trPublicacao')]")
# for indice in range(0, len(lista_resultados), 2):
#     link = lista_resultados[indice].xpath("./td/a[@href]").attrib['href']
#     link = f"https://sei.enap.gov.br/sei/publicacoes/{link}"
#     titulo = lista_resultados[indice + 1].xpath('./td[@colspan]/text()').get().replace('\n', ' ').strip().split('  ')[0]
#     # edicao = lista_resultados[indice].xpath("./td[3]/text()").get()
#     boletim = lista_resultados[indice].xpath("./td[4]/text()").get()
#     data = lista_resultados[indice].xpath("./td[5]/text()").get()
#     texto = lista_resultados[indice].xpath("./td[8]/text()").get()
#     resumo = texto or ''
#     section = f"{boletim} - {data}"
#     result.append({"href": link, "section": section, "date": '', "title": titulo, "abstract": resumo})
#
#     # match['section'],
#     # match['href'],
#     # match['title'],
#     # match['abstract'],
#     # match['date'])
#
#
# data = {
# 'orgao': '956',
# 'dtpubini': '20/09/2023'.replace('/','-'),
# 'dtpubfim': '20/09/2023'.replace('/','-'),
# }
# r = requests.get('https://boletim.sigepe.gov.br/sigepe-bgp-ws-publicacao/publicacao-service/',params=data)
#
# lista_resultados = json.loads(r.text)
# # lista = []
# for lei in lista_resultados['response']['docs']:
#     link = f"https://boletim.sigepe.gov.br/publicacao/detalhar/{lei['metadados']['IDATO']}"
#     edicao = f"Ano {lei['metadados']['ANO']}, Edição {lei['metadados']['MES']}.{lei['metadados']['SEQUENCIAL']}"
#     data =  lei['metadados']['DTPUBLICACAOATO']
#     titulo = (f"{lei['metadados']['NMESPECIEATO']} {lei['metadados']['SGUORGPRINCIPAL']}/{lei['metadados']['SGORGPRINCIPAL']} n° "
#         f"{lei['metadados']['NUMATO']}/{lei['metadados']['ANOCADASTROATO']}")
#     resumo = lei['metadados']['EMENTAATO']
#     section = f"SIGEPE - Boletim de Gestão de Pessoas - {data}, {edicao}"
#     result.append({"href": link, "section": section, "date": '', "title": titulo, "abstract": resumo})
#
# pass



from airflow.utils.email import send_email
import pandas as pd


def generate_email_content() -> str:
    """Generate HTML content to be sent by email based on
    search_report dictionary
    """
    try:
        current_directory = os.path.dirname(__file__)
        file_path_template_email = os.path.join(current_directory, 'src','template_email.html')
        file_path_template_item_email = os.path.join(current_directory,'src', 'template_item_email.html')

        conteudo = ''
        with open(file_path_template_email, 'r') as template:
            conteudo = f'{template.read()}'

        item_str = ''
        with open(file_path_template_item_email, 'r') as item_template:
            item_str = item_template.read()

        texto = ''
        for group, results in busca.items():
            for term, items in results.items():
                for item in items:
                    texto += ((item_str.replace('{{link}}', item['href'])
                               .replace('{{section}}', item['section'])
                               .replace('{{date}}', item['date']))
                              .replace("{{title}}", item['title'])
                              .replace("{{abstract}}", item['abstract'])
                              )

        conteudo = conteudo.replace('{{conteudo}}', texto)
        conteudo = conteudo.replace('{{hoje}}', datetime.now().strftime('%d/%m/%Y'))
        return conteudo
    except Exception as e:
        return str(e)


def convert_report_to_dataframe() -> pd.DataFrame:
    df = pd.DataFrame()
    df.columns = ['Grupo', 'Termo de pesquisa', 'Seção', 'URL']

    return df

def get_pdf_tempfile() -> NamedTemporaryFile:
    temp_file = NamedTemporaryFile(prefix='extracao_', suffix='.pdf',  delete=False)
    conteudo = generate_email_content()
    pdf = pdfkit.from_string(conteudo, False)
    temp_file.file.write(pdf)
    return temp_file


files=[]
with get_pdf_tempfile() as pdf_file:
    files.append(pdf_file.name)

body = 'sdsd'
pdfkit.from_string(body, False)


send_email(
    to='teste@teste.com',
    subject='full_subject oi mundo',
    files=files,
    html_content='content oi',
    mime_charset='utf-8')

# path to your wkhtmltopdf.exe file
# wkhtml_to_pdf = os.path.join('C:\\Program Files\\wkhtmltopdf\\bin',"wkhtmltopdf.exe")
#
#
options = {
    'page-size': 'A4',
    'page-height': "13in",
    'page-width': "10in",
    'margin-top': '0in',
    'margin-right': '0in',
    'margin-bottom': '0in',
    'margin-left': '0in',
    'encoding': "UTF-8",
    'no-outline': None
}
#
# template_path = 'pdf_template.html'
#
# context = {"name": "Areeba Seher"}
# html = "sdsdsdsd sdsd"
#
# config = pdfkit.configuration(wkhtmltopdf=wkhtml_to_pdf)
#
# pdf = pdfkit.from_string(html, False, configuration=config, options=options)

pass
