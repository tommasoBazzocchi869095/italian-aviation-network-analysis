import dash
from dash import dcc, html
import plotly.graph_objects as go
import pandas as pd
import igraph as ig

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


def calculate_metrics(g):
    giant_component_size = max(g.connected_components().sizes())
    diameter = g.diameter()
    avg_path_length = g.average_path_length()
    
    distances = g.shortest_paths()
    num_nodes = len(g.vs)
    efficiency_sum = 0
    count = 0
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            distance = distances[i][j]
            if distance > 0 and distance < float('inf'):
                efficiency_sum += 1 / distance
                count += 1
    efficiency = efficiency_sum / count if count > 0 else 0
    
    return {
        'giant component size': giant_component_size,
        'diameter': diameter,
        'average path length': avg_path_length,
        'efficiency': efficiency
    }

def generate_graph_for_country(country, mode='external'):
    df_routes_ori = pd.read_csv("routes.csv")
    df_routes_ori = df_routes_ori[df_routes_ori['Stops'] == 0]
    df_routes = df_routes_ori[['Source airport', 'Source airport ID', 'Destination airport', 'Destination airport ID']]

    df_airports = pd.read_csv("airports.csv")
    df_airports = df_airports[df_airports['Tz database time zone'].str.contains('Europe')]
    df_airports = df_airports[['Airport ID', 'Name', 'City', 'Country', 'Latitude', 'Longitude']]

    df_routes = df_routes[df_routes['Source airport ID'] != '\\N']
    df_routes = df_routes[df_routes['Destination airport ID'] != '\\N']
    df_routes['Source airport ID'] = df_routes['Source airport ID'].astype('int64')
    df_routes['Destination airport ID'] = df_routes['Destination airport ID'].astype('int64')

    df_merged = pd.merge(df_routes, df_airports, left_on='Source airport ID', right_on='Airport ID', how='inner')
    df_merged = df_merged.rename(columns={
        'Name': 'Source airport name',
        'City': 'Source airport city',
        'Country': 'Source airport country',
        'Latitude': 'Source Latitude',
        'Longitude': 'Source Longitude'
    })
    df_merged = df_merged.drop(columns=['Airport ID'])

    df_merged = pd.merge(df_merged, df_airports, left_on='Destination airport ID', right_on='Airport ID', how='inner')
    df_merged = df_merged.rename(columns={
        'Name': 'Destination airport name',
        'City': 'Destination airport city',
        'Country': 'Destination airport country',
        'Latitude': 'Destination Latitude',
        'Longitude': 'Destination Longitude'
    })
    df_merged = df_merged.drop(columns=['Airport ID'])

    if mode == 'internal':
        df_merged = df_merged.query(
            "`Source airport country` == @country and `Destination airport country` == @country"
        )
    elif mode == 'external':
        df_merged = df_merged.query(
            "`Source airport country` == @country or `Destination airport country` == @country"
        )
    else:
        raise ValueError("Mode deve essere 'internal' o 'external'")

    df_merged['weight'] = df_merged.duplicated(keep=False)
    df_merged['weight'] = df_merged.groupby(df_merged.columns.tolist())['weight'].transform('sum')
    df_merged = df_merged.drop_duplicates()
    df_merged['weight'] += 1
    df_merged.reset_index(drop=True, inplace=True)

    return df_merged

def create_igraph_object(df):
    edges = list(zip(df['Source airport name'], df['Destination airport name']))
    edge_weights = df['weight'].tolist()
    nodes = list(set(df['Source airport name']).union(set(df['Destination airport name'])))
    
    g = ig.Graph()
    g.add_vertices(nodes)
    g.add_edges(edges)
    
    g.es['weight'] = edge_weights
    
    g.vs['country'] = [
        df.loc[df['Source airport name'] == node, 'Source airport country'].iloc[0] 
        if node in df['Source airport name'].values 
        else df.loc[df['Destination airport name'] == node, 'Destination airport country'].iloc[0] 
        for node in nodes
    ]
    
    degree_centrality = g.strength(weights='weight')
    betweenness_centrality = g.betweenness(weights='weight')
    
    node_data = {
        vertex['name']: {
            'degree_centrality': degree_centrality[idx],
            'betweenness_centrality': betweenness_centrality[idx]
        }
        for idx, vertex in enumerate(g.vs)
    }
    
    return g, node_data

def create_scatter_plot_with_lines(df, g, node_data, centrality_metric, country, mode):
    fig = go.Figure()
    
    for _, row in df.iterrows():
        if centrality_metric == 'degree':
            line_width = row['weight']
        else:
            line_width = row['weight']
        
        color = 'blue' if row['Source airport country'] == country and row['Destination airport country'] == country else 'lightblue'
        fig.add_trace(go.Scatter(
            x=[row['Source Longitude'], row['Destination Longitude']],
            y=[row['Source Latitude'], row['Destination Latitude']],
            mode='lines',
            line=dict(width=line_width, color=color),
            opacity=0.5,
            hoverinfo='text',
            text=f"Departure: {row['Source airport name']}<br>Arrival: {row['Destination airport name']}",
            showlegend=False
        ))

    nodes_df = pd.concat([
        df[['Source Longitude', 'Source Latitude', 'Source airport name', 'Source airport country']].rename(columns={
            'Source Longitude': 'Longitude', 
            'Source Latitude': 'Latitude', 
            'Source airport name': 'Airport name', 
            'Source airport country': 'Country'
        }),
        df[['Destination Longitude', 'Destination Latitude', 'Destination airport name', 'Destination airport country']].rename(columns={
            'Destination Longitude': 'Longitude', 
            'Destination Latitude': 'Latitude', 
            'Destination airport name': 'Airport name', 
            'Destination airport country': 'Country'
        })
    ]).drop_duplicates().reset_index(drop=True)

    if mode == 'internal':
        if centrality_metric == 'degree':
            node_sizes = [node_data[node]['degree_centrality']/5 for node in nodes_df['Airport name']]
        else:
            node_sizes = [node_data[node]['betweenness_centrality']/2 for node in nodes_df['Airport name']]

    elif mode == 'external':
        if centrality_metric == 'degree':
            node_sizes = [
                node_data[node]['degree_centrality']/5 if nodes_df[nodes_df['Airport name'] == node]['Country'].values[0] == country 
                else node_data[node]['degree_centrality']/5 
                for node in nodes_df['Airport name']
            ]
        else:
            node_sizes = [
                node_data[node]['betweenness_centrality']/23 if nodes_df[nodes_df['Airport name'] == node]['Country'].values[0] == country 
                else node_data[node]['betweenness_centrality']/13 
                for node in nodes_df['Airport name']
            ]
    
    fig.add_trace(go.Scatter(
    x=nodes_df['Longitude'],
    y=nodes_df['Latitude'],
    hoverinfo='text',
    # Aggiungi il grado o la betweenness al testo di hover in base alla selezione
    text = [
    f"{row['Airport name']}<br>{centrality_metric.capitalize() if centrality_metric else 'Betweenness'} Centrality: {node_data[row['Airport name']][f'{centrality_metric}_centrality'] if centrality_metric else node_data[row['Airport name']]['betweenness_centrality']:.2f}"
    for _, row in nodes_df.iterrows()
    ],
    mode='markers',
    marker=dict(
        size=node_sizes,
        color=nodes_df['Country'].apply(lambda x: 'red' if x == country else 'green'),
        symbol='circle'
    ),
    name='Airports',
    showlegend=False
    ))


    fig.add_trace(go.Scatter(
        x=[None],
        y=[None],
        mode='markers',
        marker=dict(
            size=10,
            color='red',
            symbol='circle'
        ),
        legendgroup="Aeroporti Nazionali",
        showlegend=True,
        name="Aeroporti Nazionali"
    ))

    fig.add_trace(go.Scatter(
        x=[None],
        y=[None],
        mode='markers',
        marker=dict(
            size=10,
            color='green',
            symbol='circle'
        ),
        legendgroup="Aeroporti Internazionali",
        showlegend=True,
        name="Aeroporti Internazionali"
    ))

    fig.add_trace(go.Scatter(
        x=[None],
        y=[None],
        mode='lines',
        line=dict(width=2, color='blue'),
        legendgroup="Rotte Nazionali",
        showlegend=True,
        name="Rotte Nazionali"
    ))

    fig.add_trace(go.Scatter(
        x=[None],
        y=[None],
        mode='lines',
        line=dict(width=2, color='lightblue'),
        legendgroup="Rotte Internazionali",
        showlegend=True,
        name="Rotte Internazionali"
    ))
    fig.add_trace(go.Scatter(
        x=[None],
        y=[None],
        mode='markers',
        marker=dict(
            size=10,
            color='gray',
            symbol='x'
        ),
        legendgroup="Nodi Isolati Nazionali",
        showlegend=True,
        name="Nodi Isolati Nazionali"
    ))

    fig.add_trace(go.Scatter(
        x=[None],
        y=[None],
        mode='markers',
        marker=dict(
            size=10,
            color='orange',
            symbol='x'
        ),
        legendgroup="Nodi Isolati Internazionali",
        showlegend=True,
        name="Nodi Isolati Internazionali"
    ))
    fig.update_layout(
        showlegend=True,
        xaxis=dict(fixedrange=False),
        yaxis=dict(fixedrange=False),
        dragmode='select',
        height=800,
        margin=dict(l=0, r=0, t=50, b=0),
        legend=dict(
            x=1,
            y=1,
            traceorder='normal',
            font=dict(size=12)
        )
    )

    return fig

def simulate_attack_with_metrics(grafo, num_attacks, nomi_nodi_ordinati):
    grafo_attaccato = grafo.copy()
    metrics_during_attack = []
    
    for i in range(num_attacks + 1):
        if i > 0:
            nodo_da_rimuovere = grafo_attaccato.vs.find(name=nomi_nodi_ordinati[i - 1])
            grafo_attaccato.delete_vertices(nodo_da_rimuovere)
        
        metrics = calculate_metrics(grafo_attaccato)
        isolated_nodes_count = sum(1 for v in grafo_attaccato.vs if grafo_attaccato.degree(v.index) == 0)
        metrics['isolated nodes count'] = isolated_nodes_count
        metrics_during_attack.append(metrics)
    nodi_isolati = [v['name'] for v in grafo_attaccato.vs if grafo_attaccato.degree(v.index) == 0]
    
    return grafo_attaccato, metrics_during_attack, nodi_isolati



app.layout = html.Div([
    html.H1('Resilienza reti aeree', style={'textAlign': 'center'}),
    dcc.Tabs(id="tabs-example", value='tab-2-example', children=[
        dcc.Tab(label='Italy', value='tab-1-example'), 
        dcc.Tab(label='France', value='tab-2-example'),
    ]),
    html.Div([
        dcc.Dropdown(
            id='dropdown-menu-1',
            options=[
                {'label': 'Situazione interna', 'value': 'internal'},
                {'label': 'Situazione interna ed esterna', 'value': 'external'}
            ],
            placeholder="Seleziona un'opzione",
            style={'display': 'inline-block', 'width': '48%', 'margin-right': '10px'}
        ),
        dcc.Dropdown(
            id='dropdown-centrality',
            options=[
                {'label': 'Degree Centrality', 'value': 'degree'},
                {'label': 'Betweenness Centrality', 'value': 'betweenness'}
            ],
            placeholder="Seleziona la centralità per la dimensione dei nodi",
            style={'display': 'inline-block', 'width': '48%'}
        ),
    ], style={'display': 'flex', 'justify-content': 'space-between'}),
    html.Div(id='graph-container'),
    dcc.RadioItems(
        id='metrics-switch',
        options=[
            {'label': 'Giant Component & Diameter', 'value': 'metrics1'},
            {'label': 'Average Path Length & Efficiency', 'value': 'metrics2'}
        ],
        value='metrics1',
        labelStyle={'display': 'inline-block', 'margin-right': '20px'},
        style={'textAlign': 'center', 'margin-top': '20px'}
    ),
    html.Div(id='metrics'),
    dcc.Slider(
        id='number-slider-tab-1',
        min=0,
        max=15,
        value=0,
        step=3
    ),
])

def create_metrics_plots(metrics_during_attack):
    steps = list(range(len(metrics_during_attack)))
    
    giant_component_sizes = [metrics.get('giant component size', 0) for metrics in metrics_during_attack]
    diameters = [metrics.get('diameter', 0) for metrics in metrics_during_attack]
    avg_path_lengths = [metrics.get('average path length', 0) for metrics in metrics_during_attack]
    efficiencies = [metrics.get('efficiency', 0) for metrics in metrics_during_attack]
    isolated_nodes_counts = [metrics.get('isolated nodes count', 0) for metrics in metrics_during_attack]
    fig1 = go.Figure()

    fig1.add_trace(go.Scatter(
        x=steps,
        y=giant_component_sizes,
        mode='lines+markers',
        name='Giant Component Size',
        line=dict(color='blue')
    ))

    fig1.add_trace(go.Scatter(
        x=steps,
        y=diameters,
        mode='lines+markers',
        name='Diameter',
        line=dict(color='red')
    ))

    fig1.add_trace(go.Scatter(
        x=steps,
        y=isolated_nodes_counts,
        mode='lines+markers',
        name='Isolated Nodes',
        line=dict(color='orange')
    ))

    fig1.update_layout(
        title='Giant Component Size, Diameter, and Isolated Nodes',
        xaxis_title='Number of Attacks',
        yaxis_title='Metric Value',
        height=500,
        margin=dict(l=50, r=50, t=50, b=50)
    )

    fig2 = go.Figure()

    fig2.add_trace(go.Scatter(
        x=steps,
        y=avg_path_lengths,
        mode='lines+markers',
        name='Average Path Length',
        line=dict(color='green')
    ))

    fig2.add_trace(go.Scatter(
        x=steps,
        y=efficiencies,
        mode='lines+markers',
        name='Efficiency',
        line=dict(color='purple')
    ))

    fig2.update_layout(
        title='Average Path Length and Efficiency',
        xaxis_title='Number of Attacks',
        yaxis_title='Metric Value',
        height=500,
        margin=dict(l=50, r=50, t=50, b=50)
    )

    return fig1, fig2

@app.callback(
        
    [dash.dependencies.Output('graph-container', 'children'),
    dash.dependencies.Output('metrics', 'children')],
    [
        dash.dependencies.Input('tabs-example', 'value'),
        dash.dependencies.Input('dropdown-menu-1', 'value'),
        dash.dependencies.Input('dropdown-centrality', 'value'),
        dash.dependencies.Input('number-slider-tab-1', 'value'),
        dash.dependencies.Input('metrics-switch', 'value')
    ]
)
def update_graph(tab_name, dropdown_menu_1, centrality_metric, num_attacks,selected_metrics):
    country = 'France' if tab_name == 'tab-2-example' else 'Italy'
    
    if dropdown_menu_1 is None:
        return html.Div([
            html.H3("Seleziona una delle opzioni per visualizzare il grafo")
        ]), None
    
    mode = dropdown_menu_1
    
    df = generate_graph_for_country(country, mode=mode)
    
    if df.empty:
        return html.Div([
            html.H3("Nessun dato disponibile per la selezione effettuata")
        ]), None
    
    g, node_data = create_igraph_object(df)
    clusters = g.clusters()
    giant_component = clusters.giant()
    
    stati_prima = set(df[df['Source airport name'].isin(giant_component.vs['name'])]['Source airport country']).union(
                  set(df[df['Destination airport name'].isin(giant_component.vs['name'])]['Destination airport country']))

    if centrality_metric == 'degree':
        nomi_nodi_ordinati = sorted(node_data, key=lambda x: -node_data[x]['degree_centrality'])
    else:
        nomi_nodi_ordinati = sorted(node_data, key=lambda x: -node_data[x]['betweenness_centrality'])

    g_attacked, metrics_during_attack, nodi_isolati = simulate_attack_with_metrics(g, num_attacks, nomi_nodi_ordinati)
    
    clusters_after_attack = g_attacked.clusters()
    giant_component_after_attack = clusters_after_attack.giant()
    
    stati_dopo = set(df[df['Source airport name'].isin(giant_component_after_attack.vs['name'])]['Source airport country']).union(
                 set(df[df['Destination airport name'].isin(giant_component_after_attack.vs['name'])]['Destination airport country']))

    stati_fuori_giant_component = stati_prima - stati_dopo

    metrics = calculate_metrics(g_attacked)
    metrics = {
        'Paesi fuori dalla giant component': ', '.join(stati_fuori_giant_component) if stati_fuori_giant_component else 'Nessuno',
        **metrics
    }

    nodi_rimanenti = set(g_attacked.vs['name'])
    df_edges = df[(df['Source airport name'].isin(nodi_rimanenti)) & (df['Destination airport name'].isin(nodi_rimanenti))]

    fig = create_scatter_plot_with_lines(df_edges, g_attacked, node_data, centrality_metric, country, mode=mode)
    fig_metrics1, fig_metrics2 = create_metrics_plots(metrics_during_attack)
    if selected_metrics == 'metrics1':
        metrics_graph = dcc.Graph(figure=fig_metrics1)
    else:
        metrics_graph = dcc.Graph(figure=fig_metrics2)

    nodi_isolati_info = {
        'Longitude': [],
        'Latitude': [],
        'Airport name': [],
        'Country': [],
        'Color': []
    }

    for nodo in nodi_isolati:
        if nodo in df['Source airport name'].values:
            nodo_info = df[df['Source airport name'] == nodo]
            nodi_isolati_info['Longitude'].append(nodo_info['Source Longitude'].iloc[0])
            nodi_isolati_info['Latitude'].append(nodo_info['Source Latitude'].iloc[0])
            nodi_isolati_info['Airport name'].append(nodo)
            nodi_isolati_info['Country'].append(nodo_info['Source airport country'].iloc[0])
            nodi_isolati_info['Color'].append('gray' if nodo_info['Source airport country'].iloc[0] == country else 'orange')
        elif nodo in df['Destination airport name'].values:
            nodo_info = df[df['Destination airport name'] == nodo]
            nodi_isolati_info['Longitude'].append(nodo_info['Destination Longitude'].iloc[0])
            nodi_isolati_info['Latitude'].append(nodo_info['Destination Latitude'].iloc[0])
            nodi_isolati_info['Airport name'].append(nodo)
            nodi_isolati_info['Country'].append(nodo_info['Destination airport country'].iloc[0])
            nodi_isolati_info['Color'].append('gray' if nodo_info['Destination airport country'].iloc[0] == country else 'orange')

    if nodi_isolati_info['Airport name']:
        fig.add_trace(go.Scatter(
            x=nodi_isolati_info['Longitude'],
            y=nodi_isolati_info['Latitude'],
            mode='markers',
            marker=dict(
                size=10,
                color=nodi_isolati_info['Color'],
                symbol='x'
            ),
            hoverinfo='text',
            text=nodi_isolati_info['Airport name'],
            name='Nodi Isolati',
            showlegend=False
        ))

    annotations = []
    y_pos = 0.95
    for metric_name, metric_value in metrics.items():
        annotations.append(dict(
            x=0,
            y=y_pos,
            xref='paper',
            yref='paper',
            text=f"<b>{metric_name}:</b> {metric_value:.2f}" if isinstance(metric_value, (int, float)) else f"<b>{metric_name}:</b> {metric_value}",
            showarrow=False,
            font=dict(size=12, color='black'),
            align='left',
            textangle=0,
            xanchor='left',
            yanchor='top'
        ))
        y_pos -= 0.05
    
    fig.update_layout(annotations=annotations)

    return dcc.Graph(figure=fig), metrics_graph

if __name__ == '__main__':
    app.run_server(debug=True)