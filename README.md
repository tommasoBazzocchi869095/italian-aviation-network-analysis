# Resilience and Topology Analysis of Air Networks: Italy vs. France

## Overview
This project implements a comparative analysis based on graph theory to evaluate the robustness and resilience of the airport infrastructures of Italy and France. Starting from the premise that the French network is considered among the most efficient in Europe, the study investigates how the two topologies react under operational stress conditions.

## Scope of Analysis
The analysis is structured across two geographic levels:
* **National Scenario:** Focused exclusively on domestic air traffic.
* **European Scenario:** Extended to direct connections with other airports on the continent, to assess the risk of international isolation.

## Methodology
Leveraging the *Global Air Transportation Network Mapping* dataset, we constructed weighted graphs where nodes represent airports and edges represent routes (or specific airlines). The project calculates fundamental Network Analysis metrics, including:
* Degree Centrality
* Betweenness Centrality
* Global Efficiency
* Assortativity
* Variations of the Giant Component

## Simulated Attacks
To test structural resilience, the code simulates various types of "attacks" on the network:
* **Airport Attacks (Node Removal):** Random tests and targeted attacks (removing nodes with the highest degree and betweenness centrality values).
* **Airline Attacks (Edge/Subnetwork Removal):** Random tests and targeted attacks based on the volume of flights managed by individual airlines (e.g., Ryanair, Air France, Alitalia).

## Key Findings
Although both networks exhibit a disassortative *hub-and-spoke* topology, the simulations reveal that the Italian network is more resilient to targeted attacks compared to the French one. Thanks to a lower disassortativity coefficient, the Italian infrastructure undergoes a slower fragmentation process, better preserving global connectivity and isolating a significantly lower number of airports and connected nations.
