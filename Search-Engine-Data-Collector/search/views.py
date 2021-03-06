'''
Main module responsible for website backend logic
...
Attributes
----------
rf: NGramClassification
    The variable containing the model
current_links: list(str)
    A list of linked inputted in the case of a user uploading a CSV file of search queries
current_title_and_desc: list(tuple(str, str))
    A list of the title and description of the research results tuples in that specific order
current_object: str
    The object the user is quering on, cannot be changed once set
data_x: list(int)
    A list representing the X axis of the graph displayed on the home. This is just arange(0, len(past_accuracy))
past_accuracy: list(int)
    A list of accuracies outputted from the model after each annotation
past_recall: list(int)
    A list of recalls outputted from the model after each annotation
past_precision: list(int)
    A list of precisions outputted from the model after each annotation
past_f1: list(int)
    A list of f1 scores outputted from the model after each annotation
query: str
    The query built from the user inputs in the case of a user manual input
queries: list(str)
    The list of queries in the case the user uploads a CSV of queries
dic_t: dictionary
    A dictionary mapping a object to its corresponding search template

Methods
-------
'''
from django.http.response import HttpResponseRedirect
from django.shortcuts import render
from django.http import HttpResponse
from .forms import QueryForm, UploadFileForm
#from .source.rf import RFCalculator
from .source.ml_model import MLModel
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup as Soup
import bs4
from BetterGoogleSearch.search import GoogleSearch, SearchError
import re
rf = MLModel()
current_links = []
current_title_and_desc = []
current_object = ""
data_x = []
past_accuracy = []
past_recall = []
past_precision = []
past_f1 = []
query = ""
queries = []
dict_t = {
    "Professor": ["First Name", "Last Name", "Institution"],
    "Movie": ["Name", "Year"],
    "Electronic": ["Name", "Model No./Year"],
    "Car": ["Make", "Model", "Year"]
}

def clean_title_and_desc(title, desc):
    '''
    Helper function that properly formates the title and description to only include letters, numbers, and spaces
    Parameters
    ----------
    title: str
        The title of a search result
    desc: str
        The description of a search result
    Returns
    -------
    tuple(str, str)
        A tuple of the cleaned title and description
    '''
    title_ = title.lower().strip()
    desc_ = desc.lower().strip()
    title_ = re.sub(r'[^a-zA-Z0-9 ]', '', title_) #this removes spaces, may need to be changed in the future if using a different feature method
    desc_ = re.sub(r'[^a-zA-Z0-9 ]', '', desc_)
    return title_, desc_

def set_links_title_desc(results, divs):
    '''
    Helper function that extracts the title and description of a list of divs from the Google search result page
    Parameters
    ----------
    results: xgoogle.search.SearchResult
        A search result object from xgoogle contining the title, url, and description
    divs: list(bs4.element)
        A list of bs4 elements representing divs from the Google search result page
    Returns
    -------
    list(bs4.element)
        A list of cleaned and formatted divs
    '''
    str_divs = []
    global current_links
    global current_title_and_desc
    current_links.clear()
    current_title_and_desc.clear()
    for i in range(len(results)):
        #print(results[i].url)
        if (results[i].url[0] == '/'):
            continue
        current_links.append(results[i].url)
        current_title_and_desc.append(clean_title_and_desc(results[i].title, results[i].desc))
        for descendant in divs[i].descendants:
            if descendant != "" and descendant != " " and not isinstance(descendant, bs4.element.NavigableString) and descendant.has_attr('href'):
                descendant['href'] = current_links[-1]
                descendant['target'] = "_blank"
                descendant['rel'] = 'noopener noreferrer'
                
        str_divs.append(divs[i])
        if len(current_links) >=10:
            break
    return str_divs

def home(request):
    '''
    Function that renders the homepage of the website
    Returns
    -------
    HTML: search/home.html
    '''
    context = {'model': rf.model, 'num_datapoints': len(rf.labels), 'class_count': rf.get_class_count()}
    return render(request, 'search/home.html', context=context)

def no_words(request, annotation):
    return edit(request, annotation, "")

def edit(request, annotation, words):
    '''
    Function that handles the user's submitted annotations and renders the homepage of the website
    Parameters
    ----------
    annotation: str
        A list of either 0's or 1's where 0 is not a hompeage and 1 is a homepage
    words: str
        A string of words with each word seperated by a '~'
    Returns
    -------
    HTML: search/home.html
    '''
    for word in words.split('~'):
        if word == '':
            continue
        rf.add_word(word)

    truths = [int(c) for c in annotation]
    
    
    global current_links
    global current_title_and_desc
    global query
    for i in range(len(current_links)):
        rf.add_datapoint(current_links[i], current_title_and_desc[i][1], truths[i], current_title_and_desc[i][0], i, query)
    data = rf.generate_random_forest()
    past_accuracy.append(data[0])
    past_recall.append(data[1])
    past_precision.append(data[2])
    past_f1.append(data[3])
    data_x.append(len(past_accuracy))
    print(past_accuracy, past_recall, past_precision, past_f1)
    rf.download_dataset()
    if len(queries) != 0:
        query = queries.pop(0)
        return handle_query(request)
    return render(request, 'search/home.html', {'stats_local': data, 'data_x': data_x, 
    'past_accuracy': past_accuracy, 'past_f1': past_f1, 'past_precision': past_precision, 
    'past_recall': past_recall, 'order': ['not_homepage', 'homepage'], 'model': rf.model, 'num_datapoints': len(rf.labels), 'class_count': rf.get_class_count(), 'object': current_object})

def handle_input(request):
    '''
    Function that handles the user's manual query input & renders the annotaton page
    Returns
    -------
    HTML: search/iframe_page.html
    '''
    print("triggered")
    if request.method == 'POST':
        print("POST request")
        form = QueryForm(request.POST)
        if form.is_valid():
            global query
            query = str(form['q1'].value()) + " " + str(form['q2'].value()) + " " + str(form['q3'].value()) + " " + str(form['q4'].value()) + " " + str(form['q5'].value()) + " " + str(form['q6'].value())
            query = query.strip()
            global current_object
            current_object = "" + str(form['your_object'].value())
            return handle_query(request)
        else:
            return render(request, 'search/home.html', context={'error': 'Form submission not valid'})
    print(request.method)
    return render(request, 'search/home.html', context={'error': 'POST request was not made'})

def file_upload(request):
    '''
    Function that handles the user's CSV file upload & renders the annotation page
    Returns
    -------
    HTML: search/iframe_page.html
    '''
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        
        if form.is_valid():
            global current_object
            current_object = str(form['file_object'].value())
            csv_file = request.FILES['file']
            if not csv_file.name.endswith('.csv'):
                return render(request, 'search/home.html', context={'error': 'File is not a CSV'})
            csv_data = csv_file.read().decode("utf-8")
            
            lines = list(map(str.rstrip, csv_data.split("\n")))
            if current_object not in dict_t: #error
                return render(request, 'search/home.html', context={'error': 'Object not in dict, update dic_t in views.py?'})
            input_names = lines[0].split(',')
            for i in range(len(dict_t[current_object])):
                if dict_t[current_object][i] != input_names[i]:
                    return render(request, 'search/home.html', context={'error': 'File is not formatted properly to the object'})

            for i in range(1, len(lines)):
                if lines[i] != "":
                    fields = []
                    for field in lines[i].split(','):
                        if field != "":
                            fields.append(field)
                    if len(fields) < len(dict_t[current_object]):# less fields than required
                        return render(request, 'search/home.html', context={'error': 'Not enough fields on line ' + str(i) + ' of the uploaded CSV'})
                    temp_query = ""
                    for field in fields:
                        temp_query += field + " "
                    temp_query = temp_query.strip()
                    queries.append(temp_query)
            print(queries)
        else:
            return render(request, 'search/home.html', context={'error': 'Form submission not valid'})
    else:
        return render(request, 'search/home.html', context={'error': 'POST request was not made'})
    if len(queries) == 0:
        print("no queries")
        return render(request, 'search/home.html', context={'error': 'File had no valid queries'})
    global query
    query = queries.pop(0)
    return handle_query(request)

def handle_query(request):
    '''
    Helper function that renders the iframe_page give the query global variable
    Returns
    -------
    HTML: search/iframe_page.html
    '''
    try:
        gs = GoogleSearch(query)
        gs.results_per_page = 15
        results, divs = gs.get_results()
        str_divs_ = set_links_title_desc(results, divs)
        str_divs = [str(x) for x in str_divs_]
    except SearchError:
        return render(request, 'search/home.html', context={'error': 'Error while using Google search engine with query: ' + query})
            
    labels = []
    if not rf.is_empty(): #create annotations
        labels = rf.predict(current_links, [x[1] for x in current_title_and_desc], [x[0] for x in current_title_and_desc], query)
    return render(request, 'search/iframe_page.html', {'links': current_links,
     'divs': str_divs, 'labels': labels, 'model': rf.model,'data_x': data_x, 
    'past_accuracy': past_accuracy, 'past_f1': past_f1, 'past_precision': past_precision, 
    'past_recall': past_recall, 'order': ['not_homepage', 'homepage'], 'class_count': rf.get_class_count()})

def download_dataset(request):
    '''
    Function that handles when the user attempts to download the dataset from the website
    Returns
    -------
    File: CSV of dataset
    '''
    path = rf.download_dataset()
    response = HttpResponse(open(path, 'rb').read())
    response['Content-Type'] = 'text/plain'
    response['Content-Disposition'] = 'attachment; filename=search_dataset.csv'
    return response


def change_model(request, model):
    '''
    Function that handles when the user attempts to change the current model type
    Parameters
    ----------
    model: str
        The name of the model to change to
    Returns
    -------
    HTML: search/home.html
    '''
    if 'ML Models' not in model:
        rf.model = model
    if not rf.is_empty():
        data = rf.generate_random_forest()
        past_accuracy.append(data[0])
        past_recall.append(data[1])
        past_precision.append(data[2])
        past_f1.append(data[3])
        data_x.append(len(past_accuracy))
       
            
    return render(request, 'search/home.html', {'data_x': data_x,
         'past_accuracy': past_accuracy, 'past_f1': past_f1, 'past_precision': past_precision,
          'past_recall': past_recall, 'order': ['not_homepage', 'homepage'], 'num_datapoints': len(rf.labels), 'model': rf.model,
          'class_count': rf.get_class_count(), 'object': current_object})

def download_model(request):
    '''
    Function that handles when the user attempts to download the curent model
    Returns
    -------
    File: Pickle file of the model
    '''
    if rf.is_empty():
        return render(request, 'search/home.html')
    path = rf.download_model()
    response = HttpResponse(open(path, 'rb').read())
    response['Content-Type'] = 'text/plain'
    response['Content-Disposition'] = 'attachment; filename=model.pickle'
    return response