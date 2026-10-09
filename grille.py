class grille_env:
    def __init__(self, maxX, maxY , baseX, baseY , danger ):
        self.maxX = maxX
        self.maxY = maxY
        self.baseX = baseX
        self.baseY = baseY
        self.danger = set(danger)
        
    def zoneOf(self, x, y):
        midX = self.maxX / 2
        midY = self.maxY / 2
        if(x <= midX and y <= midY):
            return 1
        elif(x > midX and y <= midY):
            return 3
        elif(x <= midX and y > midY):
            return 2
        else:
            return 4
        
    def indangerZone(self, x, y):
        return (x, y) in self.danger
        
    def isInBase(self, x, y):
        return x == self.baseX and y == self.baseY
    
    def insideGrid(self, x, y):
        return 0 <= x <= self.maxX and 0 <= y <= self.maxY
    
    def voisins(self, x, y):
        candidates = [
            (x, y + 1),  # haut
            (x, y - 1),  # bas
            (x + 1, y),  # droite
            (x - 1, y)   # gauche
        ]
        voisins = []
        for nx, ny in candidates:
            if self.insideGrid(nx, ny):
                voisins.append((nx, ny))
        return voisins
    

    def display(self, droneX=None, droneY=None):
            print("\nGrille de patrouille:")
            print(f"  Dimensions: {self.maxX + 1} x {self.maxY + 1}")
            print(f"  Base: ({self.baseX}, {self.baseY})")
            print(f"  Zones dangereuses: {len(self.danger)}")
            
            # Afficher la grille
            for y in range(self.maxY, -1, -1):
                line = f"{y:2d} |"
                for x in range(self.maxX + 1):
                    if (x, y) == (droneX, droneY):
                        line += " D"
                    elif (x, y) == (self.baseX, self.baseY):
                        line += " B"
                    elif self.indangerZone(x, y):
                        line += " X"
                    else:
                        zone = self.zoneOf(x, y)
                        line += f" {zone}"
                print(line)
            
            print("   +" + "--" * (self.maxX + 1))
            print("    " + " ".join(f"{x}" for x in range(self.maxX + 1)))
            print("\nLégende: B=Base, X=Danger, 1-4=Zones")
    