"""Name pools per nationality for the roster generator (researched Oct 25; see specs/roster-generator.md).

Players are fictional; the pools are common real given names and surnames. The blocklist check in
``sim/roster.py`` stops a combination from matching a well-known real player.
"""

from sim.models import Nationality

FIRST_NAMES: dict[Nationality, list[str]] = {
    Nationality.ENGLAND: ["Jack", "Thomas", "James", "Joshua", "Daniel", "Matthew", "Samuel", "Joseph", "Callum", "William"],
    Nationality.SPAIN: ["Alejandro", "Daniel", "Pablo", "David", "Adrián", "Álvaro", "Javier", "Sergio", "Carlos", "Jorge"],
    Nationality.BRAZIL: ["Lucas", "José", "João", "Gabriel", "Matheus", "Pedro", "Rafael", "Guilherme", "Felipe", "Bruno"],
    Nationality.FRANCE: ["Thomas", "Alexandre", "Nicolas", "Lucas", "Théo", "Julien", "Kévin", "Maxime", "Quentin", "Antoine"],
    Nationality.GERMANY: ["Alexander", "Maximilian", "Lukas", "Jan", "Leon", "David", "Paul", "Daniel", "Niklas", "Felix"],
    Nationality.PORTUGAL: ["João", "Pedro", "Tiago", "Diogo", "André", "José", "Ricardo", "Luís", "Bruno", "Miguel"],
    Nationality.AUSTRIA: ["Lukas", "Michael", "Florian", "Daniel", "Alexander", "Thomas", "Stefan", "David", "Sebastian", "Philipp"],
    Nationality.NETHERLANDS: ["Thomas", "Tim", "Daan", "Max", "Niels", "Lars", "Rick", "Nick", "Tom", "Kevin"],
    Nationality.ITALY: ["Andrea", "Francesco", "Alessandro", "Matteo", "Luca", "Lorenzo", "Marco", "Davide", "Simone", "Giuseppe"],
}

SURNAMES: dict[Nationality, list[str]] = {
    Nationality.ENGLAND: ["Smith", "Jones", "Williams", "Taylor", "Brown", "Davies", "Wilson", "Evans", "Thomas", "Johnson",
                          "Roberts", "Walker", "Wright", "Robinson", "Thompson"],
    Nationality.SPAIN: ["García", "Rodríguez", "González", "Fernández", "López", "Martínez", "Sánchez", "Pérez", "Gómez",
                        "Martín", "Jiménez", "Ruiz", "Hernández", "Díaz", "Moreno"],
    Nationality.BRAZIL: ["Silva", "Santos", "Oliveira", "Souza", "Pereira", "Ferreira", "Lima", "Alves", "Rodrigues", "Costa",
                         "Gomes", "Martins", "Araújo", "Ribeiro", "Carvalho"],
    Nationality.FRANCE: ["Martin", "Bernard", "Thomas", "Petit", "Robert", "Richard", "Durand", "Dubois", "Moreau", "Laurent",
                         "Simon", "Michel", "Leroy", "Lefebvre", "Garcia"],
    Nationality.GERMANY: ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Schulz",
                          "Hoffmann", "Schäfer", "Koch", "Bauer", "Richter", "Klein", "Wolf", "Schröder", "Neumann",
                          "Schwarz", "Zimmermann"],
    Nationality.PORTUGAL: ["Silva", "Santos", "Ferreira", "Pereira", "Costa", "Oliveira", "Rodrigues", "Fernandes", "Sousa",
                           "Martins", "Gomes", "Lopes", "Marques", "Alves", "Almeida"],
    Nationality.AUSTRIA: ["Gruber", "Huber", "Bauer", "Wagner", "Müller", "Pichler", "Steiner", "Moser", "Mayer", "Hofer",
                          "Leitner", "Berger", "Fuchs", "Eder", "Fischer"],
    Nationality.NETHERLANDS: ["De Jong", "De Vries", "Jansen", "Van den Berg", "Van Dijk", "Bakker", "Janssen", "Visser",
                              "Smit", "Meijer", "Bos", "Mulder", "De Boer", "Vos", "Peters"],
    Nationality.ITALY: ["Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo", "Bruno", "Ricci", "Marino",
                        "Costa", "Gallo", "Conti", "Greco", "Mancini"],
}
