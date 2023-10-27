import json
import os
import sys
import json
from datetime import datetime
from tempfile import NamedTemporaryFile

import pandas as pd
import pdfkit
import requests
from airflow.utils.email import send_email
from notification.isender import ISender
from parsel import Selector

# TODO fix this
# Add parent folder to sys.path in order to be able to import
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)



class EmailSender(ISender):
    # highlight_tags = ("<span class='highlight' style='background:#FFA;'>",  "</span>")
    highlight_tags = ('', '')

    def __init__(self, specs) -> None:
        self.specs = specs

    def search_report_sei(self, report_date: str):
        result = []
        data = {'acao': 'publicacao_pesquisar',
                'acao_origem': 'publicacao_pesquisar',
                'id_orgao_publicacao': 0,
                'rdo_data_publicacao': 'E',
                'dta_inicio': report_date,
                'dta_fim': report_date,
                }
        r = requests.post('https://sei.enap.gov.br/sei/publicacoes/controlador_publicacoes.php', params=data)
        selector = Selector(text=r.text)
        lista_resultados = selector.xpath("//tr[contains(@id,'trPublicacao')]")
        for indice in range(0, len(lista_resultados), 2):
            try:
                link = lista_resultados[indice].xpath("./td/a[@href]").attrib['href']
                link = f"https://sei.enap.gov.br/sei/publicacoes/{link}"
                titulo = (lista_resultados[indice + 1].xpath('./td[@colspan]/text()')
                            .get().replace('\n', ' ').strip().split('  ')[0])
                boletim = lista_resultados[indice].xpath("./td[4]/text()").get()
                data = lista_resultados[indice].xpath("./td[5]/text()").get()
                texto = lista_resultados[indice].xpath("./td[8]/text()").get()
                resumo = texto or ''
                section = f"{boletim} - {data}"
                result.append({"href": link, "section": section, "date": '', "title": titulo, "abstract": resumo})
            except Exception as e:
                result += ['erro: '+str(e)]
        return result

    def search_report_sigep(self, report_date: str):
        result = []
        try:
            data = {
                'orgao': '956',
                'dtpubini': report_date.replace('/', '-'),
                'dtpubfim': report_date.replace('/', '-'),
            }
            r = requests.get('https://boletim.sigepe.gov.br/sigepe-bgp-ws-publicacao/publicacao-service/', params=data)
            lista_resultados = json.loads(r.text)
            for lei in lista_resultados['response']['docs']:
                link = f"https://boletim.sigepe.gov.br/publicacao/detalhar/{lei['metadados']['IDATO']}"
                edicao = f"Ano {lei['metadados']['ANO']}, Edição {lei['metadados']['MES']}.{lei['metadados']['SEQUENCIAL']}"
                data = lei['metadados']['DTPUBLICACAOATO']
                titulo = (
                    f"{lei['metadados']['NMESPECIEATO']} {lei['metadados']['SGUORGPRINCIPAL']}/{lei['metadados']['SGORGPRINCIPAL']} n° "
                    f"{lei['metadados']['NUMATO']}/{lei['metadados']['ANOCADASTROATO']}")
                resumo = lei['metadados']['EMENTAATO']
                section = f"SIGEPE - Boletim de Gestão de Pessoas - {data}, {edicao}"
                result.append({"href": link, "section": section, "date": '', "title": titulo, "abstract": resumo})
        except Exception as e:
            result += ['erro: '+str(e)]

        return result

    def send(self, search_report: dict, report_date: str):
        """Builds the email content, the CSV if applies, and send it
        """
        lista = self.search_report_sei(report_date) + self.search_report_sigep(report_date)
        search_report_sei_sigep = {'single_group': {'sei_sigep': lista}}
        search_report_sei_sigep['single_group'].update(search_report['single_group'])
        self.search_report = search_report_sei_sigep
        full_subject = f" Boletim de Legislação e Atos Normativos n.203 {''.join(report_date.split('/')[::-1])}"
        items = ['contains' for k, v in self.search_report.items() if v]
        if items:
            content = self.generate_email_content()
        else:
            if self.specs.skip_null:
                return 'skip_notification'
            content = "Nenhum dos termos pesquisados foi encontrado."

        if self.specs.attach_csv and items:
            files = []
            with self.get_csv_tempfile() as csv_file:
                files.append(csv_file.name)
                send_email(
                    to=self.specs.emails,
                    subject=full_subject,
                    files=files,
                    html_content=content,
                    mime_charset='utf-8')

        if self.specs.attach_pdf and items:
            files = []
            with self.get_pdf_tempfile() as pdf_file:
                files.append(pdf_file.name)
                send_email(
                    to=self.specs.emails,
                    subject=full_subject,
                    files=files,
                    html_content=content,
                    mime_charset='utf-8')

        if not((self.specs.attach_csv or self.specs.attach_pdf) and items):
            send_email(
                to=self.specs.emails,
                subject=full_subject,
                html_content=content,
                mime_charset='utf-8')


    def generate_email_content(self) -> str:
        """Generate HTML content to be sent by email based on
        search_report dictionary
        """
        current_directory = os.path.dirname(__file__)
        parent_directory = os.path.dirname(current_directory)
        file_path_template_email = os.path.join(parent_directory, 'template_email.html')
        file_path_template_item_email = os.path.join(parent_directory, 'template_item_email.html')

        conteudo = ''
        with open(file_path_template_email, 'r') as template:
            conteudo = f'{template.read()}'

        item_str = ''
        with open(file_path_template_item_email, 'r') as item_template:
            item_str = item_template.read()

        texto = ''
        for group, results in self.search_report.items():
            for term, items in results.items():
                for item in items:
                    texto += str(item_str.replace('{{link}}', item['href'])
                                .replace('{{section}}', item['section'])
                                .replace('{{date}}', item['date'])
                                .replace("{{title}}", item['title'])
                                .replace("{{abstract}}", item['abstract'])
                              )
        conteudo = conteudo.replace('{{conteudo}}', texto)
        conteudo = conteudo.replace('{{hoje}}', datetime.now().strftime('%d/%m/%Y'))
        return conteudo


    def get_csv_tempfile(self) -> NamedTemporaryFile:
        temp_file = NamedTemporaryFile(prefix='extracao_', suffix='.cvs')
        self.convert_report_to_dataframe().to_csv(temp_file, index=False)
        return temp_file

    def get_pdf_tempfile(self) -> NamedTemporaryFile:
        temp_file = NamedTemporaryFile(prefix='extracao_', suffix='.pdf', delete=False)
        conteudo = self.generate_email_content()
        pdf = pdfkit.from_string(conteudo, False)
        temp_file.file.write(pdf)
        return temp_file

    def convert_report_to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(self.convert_report_dict_to_tuple_list())
        df.columns = ['Grupo', 'Termo de pesquisa', 'Seção', 'URL',
                        'Título', 'Resumo', 'Data']
        if 'single_group' in self.search_report:
            del df['Grupo']
        return df

    def convert_report_dict_to_tuple_list(self) -> list:
        tuple_list = []
        for group, results in self.search_report.items():
            for term, matches in results.items():
                for match in matches:
                    tuple_list.append(repack_match(group, term, match))
        return tuple_list


def repack_match(group: str, search_term: str, match: dict) -> tuple:
    return (group,
            search_term,
            match['section'],
            match['href'],
            match['title'],
            match['abstract'],
            match['date'])
