import numpy as np
from sklearn.cluster import KMeans

class PortClustering:


    def __init__(self, n_clusters=None, random_state=42):

        self.n_clusters = n_clusters
        self.random_state = random_state

    # --------------------------------
    # Adaptive cluster count
    # --------------------------------
    def compute_cluster_count(self, ports):

        n = len(ports)

        # sqrt heuristic
        k = int(np.sqrt(n))

        return max(3, min(k, 25))

    # --------------------------------
    # Cluster ports
    # --------------------------------
    def cluster_ports(self, ports):

        coords = []
        valid_ports = []

        for p in ports:
            if p.latitude is None or p.longitude is None:
                continue

            if np.isnan(p.latitude) or np.isnan(p.longitude):
                continue

            # Check if coordinates might be swapped (lat should be [-90, 90], lon should be [-180, 180])
            lat = p.latitude
            lon = p.longitude

            # Fix swapped coordinates
            if abs(p.latitude) > 90 and abs(p.longitude) <= 90:
                lat, lon = p.longitude, p.latitude
            elif abs(p.longitude) > 180 and abs(p.latitude) <= 180:
                lat, lon = p.longitude, p.latitude

            # Validate ranges
            if abs(lat) > 90 or abs(lon) > 180:
                continue

            coords.append([lat, lon])
            valid_ports.append(p)

        coords = np.array(coords)

        # use manual cluster count if provided
        if self.n_clusters is not None:
            n_clusters = self.n_clusters
        else:
            n_clusters = self.compute_cluster_count(ports)

        model = KMeans(
            n_clusters=n_clusters,
            random_state=self.random_state,
            n_init=20
        )

        labels = model.fit_predict(coords)

        clusters = {}
        # Initialize clusters
        for i in range(n_clusters):
            clusters[i] = []

        # Assign ports with valid coordinates to clusters
        for i, label in enumerate(labels):
            clusters[label].append(valid_ports[i].id)

        # Assign ports without valid coordinates to clusters to ensure all ports are included
        all_valid_port_ids = set(p.id for p in valid_ports)
        unassigned_ports = [p for p in ports if p.id not in all_valid_port_ids]

        # Distribute unassigned ports evenly across clusters
        for i, port in enumerate(unassigned_ports):
            cluster_idx = i % n_clusters
            clusters[cluster_idx].append(port.id)

        return clusters

    # --------------------------------
    # Cluster summary
    # --------------------------------
    def cluster_summary(self, clusters, ports):

        port_lookup = {p.id: p for p in ports}

        summary = {}

        for cid, port_ids in clusters.items():

            names = [
                port_lookup[p].name
                for p in port_ids[:5]
                if p in port_lookup
            ]

            summary[cid] = {
                "num_ports": len(port_ids),
                "sample_ports": names
            }

        return summary