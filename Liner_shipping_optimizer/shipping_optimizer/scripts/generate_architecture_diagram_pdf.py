"""Rebuild System_Architecture_Diagram.pdf with large fonts and one short explanation per block.

Same four diagrams, same blocks, same flows and labels as the original; only (1) the text is much larger and horizontal,
(2) every block carries a number badge that matches a short explanation card under the diagram.
The only source is the original System_Architecture_Diagram.pdf (its blocks, flows and labels); nothing is added to the
architecture.

    pip install reportlab
    python scripts/generate_architecture_diagram_pdf.py [output.pdf]
"""
import sys

from reportlab.lib.colors import Color, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

W = 3000
BLUE, YELLOW, RED = Color(.435, .659, 1), Color(1, .867, .2), Color(1, .4, .4)
GREEN, BLACK, ORANGE = Color(.651, .937, .769), Color(.082, .082, .082), Color(1, .627, .251)
INK, GREY, NAVY = Color(.14, .14, .14), Color(.38, .38, .38), Color(.12, .22, .52)
CARD, CARD_LINE = Color(.965, .968, .975), Color(.80, .82, .85)
LEG = [("Input", BLUE), ("LLM / control agent", YELLOW), ("Processing stage", RED), ("Parallel agents", GREEN),
       ("Solver / validation", BLACK), ("Output", ORANGE)]
BOLD, REG, ITAL = "Times-Bold", "Times-Roman", "Times-Italic"
WARN = []
SHOW_NUMBERS = False      # True: number badges on the blocks and matching numbers on the explanation cards


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Ctx:
    def __init__(self, c, H, y0):
        self.c, self.H, self.y0 = c, H, y0

    def Y(self, y):                      # diagram-relative, measured from the top -> canvas y
        return self.H - (self.y0 + y)


def text_block(x, cx, cy, w, h, parts, color, tag=""):
    """Centered, wrapped, vertically centred stack of (text, font, size) parts."""
    paras, total = [], 0.0
    for t, f, s in parts:
        st = ParagraphStyle("p", fontName=f, fontSize=s, leading=s * 1.18, alignment=TA_CENTER, textColor=color)
        p = Paragraph(esc(t), st)
        _, ph = p.wrap(w, 10000)
        paras.append((p, ph))
        total += ph
    total += 7 * (len(paras) - 1)
    if total > h + 1:
        WARN.append(f"OVERFLOW {tag}: {total:.0f} > {h:.0f}")
    top = cy - total / 2
    for p, ph in paras:
        p.drawOn(x.c, cx - w / 2, x.Y(top + ph))
        top += ph + 7


def rrect(x, cx, cy, w, h, fill, r=22, stroke=None, lw=3):
    c = x.c
    c.setFillColor(fill)
    c.setStrokeColor(stroke or fill)
    c.setLineWidth(lw)
    c.roundRect(cx - w / 2, x.Y(cy + h / 2), w, h, r, fill=1, stroke=1)


def poly(x, pts, fill, stroke=None, lw=3):
    c = x.c
    c.setFillColor(fill)
    c.setStrokeColor(stroke or fill)
    c.setLineWidth(lw)
    p = c.beginPath()
    p.moveTo(pts[0][0], x.Y(pts[0][1]))
    for px, py in pts[1:]:
        p.lineTo(px, x.Y(py))
    p.close()
    c.drawPath(p, fill=1, stroke=1)


def diamond(x, cx, cy, w, h, fill=BLACK):
    poly(x, [(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)], fill)


def hexagon(x, cx, cy, w, h, fill=BLACK):
    d = h * 0.3
    poly(x, [(cx - w / 2, cy), (cx - w / 2 + d, cy - h / 2), (cx + w / 2 - d, cy - h / 2), (cx + w / 2, cy),
             (cx + w / 2 - d, cy + h / 2), (cx - w / 2 + d, cy + h / 2)], fill, Color(.55, .55, .55), 2)


def chevron(x, left, cy, w, h, fill=BLACK, tip=42):
    poly(x, [(left, cy - h / 2), (left + w - tip, cy - h / 2), (left + w, cy), (left + w - tip, cy + h / 2),
             (left, cy + h / 2)], fill)


def line(x, pts, lw=3.2, color=BLACK):
    c = x.c
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.setLineJoin(1)
    p = c.beginPath()
    p.moveTo(pts[0][0], x.Y(pts[0][1]))
    for px, py in pts[1:]:
        p.lineTo(px, x.Y(py))
    c.drawPath(p, fill=0, stroke=1)


def arrow(x, pts, head=22, lw=3.2):
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    n = (dx * dx + dy * dy) ** 0.5 or 1.0
    ux, uy = dx / n, dy / n
    base = (x2 - ux * head, y2 - uy * head)
    line(x, pts[:-1] + [base], lw)
    px, py = -uy, ux
    poly(x, [(x2, y2), (base[0] + px * head * .42, base[1] + py * head * .42),
             (base[0] - px * head * .42, base[1] - py * head * .42)], BLACK, BLACK, 1)


def badge(x, bx, by, label, r=27):
    if not SHOW_NUMBERS:
        return
    c = x.c
    c.setFillColor(NAVY)
    c.setStrokeColor(white)
    c.setLineWidth(3.5)
    c.circle(bx, x.Y(by), r, fill=1, stroke=1)
    c.setFillColor(white)
    c.setFont(BOLD, 30 if len(label) == 1 else 27)
    c.drawCentredString(bx, x.Y(by) - 10, label)


def label(x, cx, cy, txt, font, size, color=INK, align="c"):
    c = x.c
    c.setFillColor(color)
    c.setFont(font, size)
    (c.drawCentredString if align == "c" else c.drawString)(cx, x.Y(cy) - size * 0.3, txt)


def block(x, kind, cx, cy, w, h, title, sub, num=None, tsize=30, ssize=24, extra=None, bpos=None, tag=None):
    """Draw one block. kind: blue/yellow/orange (rounded box) | bar | pill | chevron (cx = left edge) | diamond | hexagon."""
    fills = {"blue": BLUE, "yellow": YELLOW, "orange": ORANGE, "bar": RED, "pill": GREEN, "black": BLACK}
    if kind == "bar":
        tsize = min(tsize, 27)
    tag = tag or title
    if kind in ("blue", "yellow", "orange"):
        rrect(x, cx, cy, w, h, fills[kind])
        col, tw, th, ox = INK, w - 30, h - 20, cx
        bp = bpos or (cx - w / 2 + 6, cy - h / 2 + 6)
    elif kind == "bar":
        rrect(x, cx, cy, w, h, RED, 18)
        col, tw, th, ox = white, w - 24, h - 30, cx
        bp = bpos or (cx - w / 2 + 6, cy - h / 2 + 6)
    elif kind == "pill":
        rrect(x, cx, cy, w, h, GREEN, h / 2, BLACK, 2.6)
        col, tw, th, ox = INK, w - 70, h - 14, cx
        bp = bpos or (cx - w / 2 + 14, cy - h / 2 + 8)
    elif kind == "chevron":          # cx is the left edge
        chevron(x, cx, cy, w, h)
        col, tw, th, ox = white, w - 80, h - 12, cx + (w - 30) / 2
        bp = bpos or (cx + 6, cy - h / 2 + 6)
    elif kind == "diamond":
        diamond(x, cx, cy, w, h)
        col, tw, th, ox = white, w * 0.56, h * 0.58, cx
        bp = bpos or (cx - w / 4, cy - h / 4)
    elif kind == "hexagon":
        hexagon(x, cx, cy, w, h)
        col, tw, th, ox = white, w * 0.66, h - 20, cx
        bp = bpos or (cx - w / 2 + h * 0.3, cy - h / 2 + 6)
    parts = [(title, BOLD, tsize)] + extra_parts(extra) + ([(sub, REG, ssize)] if sub else [])
    text_block(x, ox, cy, tw, th, parts, col, tag)
    if num is not None:
        badge(x, bp[0], bp[1], str(num))


def extra_parts(extra):
    return [(extra, REG, 26)] if extra else []


def arrow_label(x, cx, ytxt, big, small, ysmall, num, bx):
    label(x, cx, ytxt, big, REG, 46)
    label(x, cx, ysmall, small, ITAL, 24, GREY)
    badge(x, bx, ytxt, str(num))


# ----------------------------------------------------------------------------------------------------------------
# page definitions: (title, subtitle, diagram_height, draw(x), cards, footer_note_in_cards)
# card = (badge, title, text, color)
# ----------------------------------------------------------------------------------------------------------------
def page1(x):
    yc = 650
    # arrows first (under the blocks)
    arrow(x, [(270, yc), (330, yc)])
    arrow(x, [(640, yc), (700, yc)])
    line(x, [(930, yc), (970, yc)])
    line(x, [(970, yc - 215), (970, yc + 215)])
    for dy in (-215, 0, 215):
        arrow(x, [(970, yc + dy), (1010, yc + dy)], head=18)
    for dy in (-215, 0, 215):
        line(x, [(1290, yc + dy), (1330, yc + dy)])
    line(x, [(1330, yc - 215), (1330, yc + 215)])
    arrow(x, [(1330, yc), (1370, yc)], head=18)
    arrow(x, [(1600, yc), (1660, yc)])
    for dy in (-205, 0, 205):
        line(x, [(2210, yc + dy), (2240, yc + dy)])
    line(x, [(2240, yc - 205), (2240, yc + 205)])
    arrow(x, [(2240, yc), (2290, yc)], head=18)
    arrow(x, [(2610, yc), (2650, yc)], head=18)
    # resolutions (top) and feedbacks (bottom)
    arrow(x, [(485, yc - 150), (485, 150), (2800, 150), (2800, yc - 175)])
    yfb = yc + 440
    line(x, [(2800, yc + 175), (2800, yfb)])
    arrow(x, [(2800, yfb), (485, yfb), (485, yc + 150)])
    arrow(x, [(2800, yfb), (2800, yfb + 105)], head=22)
    # blocks
    block(x, "blue", 155, yc, 230, 270, "Inputs", "ports - OD demand - distances - fleet - port and canal costs", 1)
    block(x, "yellow", 485, yc, 310, 300, "Orchestrator Agent", "analysis - iteration control - final selection", 2,
          extra="(LLM)")
    block(x, "bar", 815, yc, 230, 600, "Problem Decomposition", "k-means port clusters - demand split by origin", 3)
    for i, dy in enumerate((-215, 0, 215), 1):
        block(x, "pill", 1150, yc + dy, 280, 130, f"Regional Agent-{i}", "", 4, tsize=29)
    label(x, 1150, yc + 345, "regional agents run in parallel", ITAL, 24, GREY)
    block(x, "bar", 1485, yc, 230, 600, "Candidate Services & Frequencies", "rotations - class screening - GA - regional MILP", 5)
    block(x, "bar", 1775, yc, 230, 640, "Global Network Optimisation", "pooled candidates - one network MILP over all demand", 6)
    block(x, "chevron", 1890, yc - 205, 320, 190, "Network MILP", "LP bound - integer plan", 7, tsize=29)
    block(x, "chevron", 1890, yc, 320, 190, "Local Search & Flow Re-optimisation", "exact LP moves", 8, tsize=26, ssize=22)
    block(x, "chevron", 1890, yc + 205, 320, 190, "Profit-floor Repair", "only if profit < 0", 9, tsize=29)
    block(x, "hexagon", 2450, yc, 320, 380, "Independent Ledger Validator Agent",
          "revenue - six cost items - profit - every constraint", 10, tsize=27, ssize=22)
    block(x, "diamond", 2800, yc, 300, 350, "Coordinator Decision Agent", "", 11, tsize=27)
    block(x, "orange", 2450, yfb + 215, 900, 220, "OPTIMISED NETWORK SOLUTION",
          "services - frequencies - vessels - cargo flows - revenue - costs - profit - coverage", 12, tsize=34, ssize=26)
    arrow_label(x, 1650, 95, "Resolutions", "regional results and context to the Coordinator: conflict detection - overlap resolution - consensus weights",
                195, 13, 1160)
    arrow_label(x, 1230, yfb + 70, "Feedbacks",
                "coverage gap - profit gap - conflicts - objective weights - rerun signal (3 iterations, best one selected)",
                yfb + 125, 14, 1075)


P1_CARDS = [
    ("1", "Inputs", "The data the system starts from: ports, origin-destination (OD) demand, distances, the fleet, and port and canal costs.", BLUE),
    ("2", "Orchestrator Agent (LLM)", "The controller of the whole system. It analyses the problem, controls the iterations (3 iterations) and makes the final selection of the best one. It uses an LLM, with the rule-based fallback of the LLM layer (page 4).", YELLOW),
    ("3", "Problem Decomposition", "Splits the global problem into regional sub-problems: ports are grouped by k-means clustering into 3 regions and the demand is assigned to a region by its origin.", RED),
    ("4", "Regional Agent-1, -2, -3", "One agent per region, all running in parallel. Each one generates candidate services, selects them with genetic algorithms and allocates cargo with a regional MILP.", GREEN),
    ("5", "Candidate Services & Frequencies", "What the regional agents hand over: the screened service rotations, the frequencies chosen by the GA and the regional MILP results. They become the candidate pool of the global stage.", RED),
    ("6", "Global Network Optimisation", "Pools the candidates of all regions and solves one network over all demand. Its verified result replaces the regional economics. Network MILP, Local Search & Flow Re-optimisation and Profit-floor Repair are the steps inside it.", RED),
    ("7", "Network MILP", "The integer optimisation that chooses services, frequencies and vessels and routes the cargo to maximise profit. The LP bound shows how much better a plan could still be.", BLACK),
    ("8", "Local Search & Flow Re-optimisation", "Improves the MILP plan with exact LP moves (add, drop or change the frequency of a service) and re-routes cargo over all valid paths while the network stays fixed.", BLACK),
    ("9", "Profit-floor Repair", "A safety step that runs only if the plan's profit is below zero, to bring it back to the profit floor.", BLACK),
    ("10", "Independent Ledger Validator Agent", "Recomputes revenue, the six cost items, profit and every constraint from the raw data, separately from the optimiser. Only verified figures are reported.", BLACK),
    ("11", "Coordinator Decision Agent", "Receives the regional results and the verified plan. It detects conflicts and overlaps, resolves them, derives consensus weights and produces the feedback for the next iteration.", BLACK),
    ("12", "Optimised Network Solution", "The final output: services, frequencies, vessels, cargo flows, revenue, costs, profit and coverage, taken from the best of the 3 iterations.", ORANGE),
    ("13", "Resolutions (top arrow)", "Regional results and context go to the Coordinator, which does conflict detection, overlap resolution and consensus weights.", INK),
    ("14", "Feedbacks (bottom arrow)", "Coverage gap, profit gap, conflicts, objective weights and a rerun signal return to the Orchestrator. The loop runs 3 iterations and the best one is selected.", INK),
]


def page2(x):
    yc = 660
    arrow(x, [(270, yc), (330, yc)])
    arrow(x, [(630, yc), (700, yc)])
    for dy in (-370, -222, -74, 74, 222, 370):
        line(x, [(1240, yc + dy), (1275, yc + dy)])
    line(x, [(1275, yc - 370), (1275, yc + 370)])
    arrow(x, [(1275, yc), (1330, yc)], head=20)
    arrow(x, [(1670, yc), (1740, yc)])
    line(x, [(1960, yc), (1995, yc)])
    line(x, [(1995, yc), (1995, yc - 185)])
    arrow(x, [(1995, yc - 185), (2040, yc - 185)], head=18)
    arrow(x, [(2190, yc - 110), (2190, yc + 110)], head=20)
    line(x, [(2340, yc + 185), (2375, yc + 185)])
    line(x, [(2375, yc + 185), (2375, yc)])
    arrow(x, [(2375, yc), (2410, yc)], head=18)
    arrow(x, [(2630, yc), (2690, yc)], head=20)
    # archetype hints (top) and feedbacks (bottom)
    arrow(x, [(480, yc - 150), (480, 135), (810, 135), (810, yc - 450)])
    yfb = yc + 540
    arrow(x, [(2825, yc + 135), (2825, yfb), (155, yfb), (155, yc + 135)])
    block(x, "blue", 155, yc, 230, 270, "Regional Problem", "own ports - demand owned by origin - full port catalogue", 1)
    block(x, "yellow", 480, yc, 300, 300, "Regional Agent", "hub detection - strategy text", 2, extra="(LLM)")
    block(x, "bar", 810, yc, 220, 900, "Service Generation", "closed rotations of distinct ports, one vessel class each", 3)
    gens = [("A", "Direct services", "top demand corridors"), ("B", "Hub loops", "multi-port via each hub"),
            ("C", "Hub trunks", "hub-to-hub rotations"), ("D", "Feeders", "spoke to best hub"),
            ("E", "Heuristic pool", "base candidates"), ("F", "Demand-coherent loops", "3-5 ports, grown from strongest ODs")]
    for (k, t, s), dy in zip(gens, (-370, -222, -74, 74, 222, 370)):
        block(x, "chevron", 920, yc + dy, 320, 140, f"{k}  {t}", s, None, tsize=25, ssize=22, tag=t)
    block(x, "diamond", 1500, yc, 340, 340, "Feasibility & Class Screening", "time - draft - canal - inventory", 4,
          tsize=25, ssize=22)
    block(x, "bar", 1850, yc, 220, 600, "Economic Filter", "cap the pool by stand-alone economics", 5)
    block(x, "pill", 2190, yc - 185, 300, 150, "Service GA", "binary selection - surrogate fitness", 6, tsize=28, ssize=22)
    block(x, "pill", 2190, yc + 185, 300, 150, "Frequency GA", "integer departures per week", 7, tsize=28, ssize=22)
    block(x, "bar", 2520, yc, 220, 600, "Regional MILP", "fixed frequencies - cargo allocation", 8)
    block(x, "orange", 2825, yc, 270, 300, "Regional result", "candidate pool - frequency hints - to the global stage", 9, tsize=29)
    arrow_label(x, 645, 50, "Archetype hints", "LLM candidate-mix suggestion, validated before use", 102, 10, 455)
    arrow_label(x, 1480, yfb + 70, "Feedbacks",
                "objective weights and regional policy from the Coordinator, applied in the next iteration", yfb + 125, 11, 1120)
    label(x, 60, yfb + 190, "Regional economics are indicative only: the global stage re-solves the pooled network and its verified figures replace them.",
          ITAL, 26, GREY, "l")


P2_CARDS = [
    ("1", "Regional Problem", "The sub-problem of one region: its own ports, the demand that originates in the region, and the full port catalogue.", BLUE),
    ("2", "Regional Agent (LLM)", "Does the hub detection and writes the strategy text for its region, using an LLM. It also receives the archetype hints (top arrow).", YELLOW),
    ("3", "Service Generation", "Creates the pool of candidate services: closed rotations of distinct ports, one vessel class each, produced by the six generators A to F.", RED),
    ("A", "Direct services", "Direct services on the top demand corridors.", BLACK),
    ("B", "Hub loops", "Multi-port loops that go via each hub.", BLACK),
    ("C", "Hub trunks", "Hub-to-hub rotations.", BLACK),
    ("D", "Feeders", "Services from a spoke port to its best hub.", BLACK),
    ("E", "Heuristic pool", "The base candidates.", BLACK),
    ("F", "Demand-coherent loops", "Loops of 3 to 5 ports grown from the strongest origin-destination flows.", BLACK),
    ("4", "Feasibility & Class Screening", "Keeps only rotations that can be sailed: it checks time, draft, canal and fleet inventory limits for the vessel class.", BLACK),
    ("5", "Economic Filter", "Caps the size of the pool by keeping the candidates with the best stand-alone economics.", RED),
    ("6", "Service GA", "Genetic algorithm that decides which services to run. A service is selected or not (binary), judged by a surrogate fitness.", GREEN),
    ("7", "Frequency GA", "Second genetic algorithm that sets the number of departures per week for each selected service.", GREEN),
    ("8", "Regional MILP", "Allocates the cargo to the selected services with the frequencies held fixed.", RED),
    ("9", "Regional result", "What the regional agent returns: its candidate pool and frequency hints, which feed the global stage.", ORANGE),
    ("10", "Archetype hints (top arrow)", "The LLM suggests a mix of service types for the candidate pool. The suggestion is validated before use.", INK),
    ("11", "Feedbacks (bottom arrow)", "Objective weights and regional policy from the Coordinator are applied in the next iteration.", INK),
]


def page3(x):
    yc = 520
    arrow(x, [(290, yc), (340, yc)])
    arrow(x, [(680, yc), (730, yc)])
    arrow(x, [(950, yc), (1000, yc)])
    for dy in (-328, -164, 0, 164, 328):
        line(x, [(1540, yc + dy), (1580, yc + dy)])
    line(x, [(1580, yc - 328), (1580, yc + 328)])
    arrow(x, [(1580, yc), (1630, yc)], head=18)
    arrow(x, [(1990, yc), (2050, yc)])
    arrow(x, [(2430, yc), (2520, yc)])
    block(x, "blue", 165, yc, 250, 270, "Candidate Pools", "from all regional agents + frequency hints", 1)
    block(x, "yellow", 510, yc, 340, 270, "Pool Union", "de-duplicate rotations - add trunk candidates for under-used vessel classes", 2)
    block(x, "bar", 840, yc, 220, 860, "Service Models", "cycle time - vessels - fuel - port calls - canal - draft", 3)
    block(x, "bar", 1110, yc, 220, 860, "OD Path Enumeration", "direct - up to 2 transfers - transit-time limit", 4)
    steps = [("LP Relaxation", "upper bound - service support", 5), ("Integer MILP", "services - frequencies - vessels - flows", 6),
             ("Local Search", "add - drop - frequency moves", 7), ("Flow Re-optimisation", "all valid paths, fixed network", 8),
             ("Profit-floor Repair", "only if profit < 0", 9)]
    for (t, s, n), dy in zip(steps, (-328, -164, 0, 164, 328)):
        block(x, "chevron", 1220, yc + dy, 320, 150, t, s, n, tsize=27, ssize=22)
    block(x, "hexagon", 1810, yc, 360, 400, "Independent Ledger",
          "re-derives revenue, every cost item and every constraint from the raw data", 10, tsize=30, ssize=22)
    block(x, "diamond", 2240, yc, 380, 400, "Verified?", "optimiser profit = ledger profit", 11, tsize=29)
    block(x, "orange", 2740, yc, 440, 290, "Verified Network Plan", "sum of regional figures equals the network total", 12,
          tsize=31)
    label(x, 2240, yc + 245, "no: plan reported as unverified", ITAL, 26, GREY)
    label(x, 1500, 1040, "Operating profit  =  Revenue  -  ( Vessel hire + Fuel + Port calls + Handling + Transshipment )", REG, 46)
    badge(x, 520, 1040, "13")
    label(x, 1500, 1100, "unserved cargo carries no penalty; checks: fleet inventory - leg capacity - demand conservation - transit time - draft - canal rules",
          ITAL, 26, GREY)


P3_CARDS = [
    ("1", "Candidate Pools", "The candidate services and frequency hints delivered by all regional agents.", BLUE),
    ("2", "Pool Union", "Merges the regional pools, removes duplicate rotations and adds trunk candidates for under-used vessel classes.", YELLOW),
    ("3", "Service Models", "Prices every candidate with one common service model: cycle time, vessels needed, fuel, port calls, and the canal and draft rules.", RED),
    ("4", "OD Path Enumeration", "Lists the routes each origin-destination pair may use: direct or with up to 2 transfers, always inside the transit-time limit.", RED),
    ("5", "LP Relaxation", "Solves the network without the integer rules to obtain an upper bound on profit and to show which services the LP supports.", BLACK),
    ("6", "Integer MILP", "Chooses the services, whole-number weekly frequencies, vessels and cargo flows that maximise profit.", BLACK),
    ("7", "Local Search", "Improves the plan with exact moves: add a service, drop a service or change a frequency.", BLACK),
    ("8", "Flow Re-optimisation", "Re-routes the cargo over all valid paths while the network itself stays fixed.", BLACK),
    ("9", "Profit-floor Repair", "Runs only if the plan's profit is below zero.", BLACK),
    ("10", "Independent Ledger", "Re-derives revenue, every cost item and every constraint from the raw data, without using the optimiser's own numbers.", BLACK),
    ("11", "Verified?", "The check: the optimiser's profit must equal the ledger's profit. If not, the plan is reported as unverified.", BLACK),
    ("12", "Verified Network Plan", "The final plan, with figures taken from the ledger. The sum of the regional figures equals the network total.", ORANGE),
    ("13", "Profit formula", "Operating profit is revenue minus vessel hire, fuel, port calls, handling and transshipment. Unserved cargo carries no penalty. The ledger also checks fleet inventory, leg capacity, demand conservation, transit time, draft and canal rules.", INK),
]


def page4(x):
    yc = 640
    arrow(x, [(290, yc), (340, yc)])
    arrow(x, [(640, yc), (700, yc)])
    line(x, [(930, yc), (965, yc)])
    line(x, [(965, yc - 225), (965, yc + 225)])
    for dy in (-225, -75, 75, 225):
        arrow(x, [(965, yc + dy), (1010, yc + dy)], head=18)
        line(x, [(1310, yc + dy), (1350, yc + dy)])
    line(x, [(1350, yc - 225), (1350, yc + 225)])
    arrow(x, [(1350, yc), (1420, yc)], head=20)
    arrow(x, [(1650, yc), (1720, yc)])
    line(x, [(2060, yc), (2110, yc)])
    line(x, [(2110, yc - 190), (2110, yc + 190)])
    arrow(x, [(2110, yc - 190), (2160, yc - 190)], head=18)
    arrow(x, [(2110, yc + 190), (2160, yc + 190)], head=18)
    line(x, [(2540, yc - 190), (2590, yc - 190), (2590, yc + 190), (2540, yc + 190)])
    arrow(x, [(2590, yc), (2640, yc)], head=18)
    arrow(x, [(490, yc - 150), (490, 135), (815, 135), (815, yc - 280)])
    yfb = yc + 440
    arrow(x, [(2800, yc + 125), (2800, yfb), (490, yfb), (490, yc + 150)])
    block(x, "blue", 165, yc, 250, 250, "Agent Request", "role - prompt - context", 1)
    block(x, "yellow", 490, yc, 300, 300, "LLM Client", "single entry point - one record per call", 2)
    block(x, "bar", 815, yc, 230, 560, "Provider Router", "role to model - cache - circuit breaker - failover", 3)
    for n, dy in zip(("OpenRouter", "Groq", "Cerebras", "Google"), (-225, -75, 75, 225)):
        block(x, "pill", 1160, yc + dy, 300, 120, n, "", 4, tsize=29)
    block(x, "bar", 1535, yc, 230, 560, "Model Response", "text or structured JSON", 5)
    block(x, "diamond", 1890, yc, 340, 340, "Validator", "schema - range - consensus rules", 6, tsize=29, ssize=22)
    block(x, "chevron", 2160, yc - 190, 380, 150, "Use LLM output", "decision source: LLM", 7, tsize=29)
    block(x, "hexagon", 2350, yc + 190, 380, 190, "Rule-based Fallback", "deterministic template or score", 8,
          tsize=27, ssize=22)
    block(x, "orange", 2800, yc, 320, 250, "Decision Applied", "source recorded: LLM or rule-based", 9, tsize=29)
    label(x, 2350, yc - 290, "accepted", ITAL, 26, GREY)
    label(x, 2350, yc + 335, "rejected or provider unavailable", ITAL, 26, GREY)
    arrow_label(x, 652, 50, "Roles", "orchestrator - regional - service generator - coordinator - iteration selector", 102, 10, 560)
    arrow_label(x, 1480, yfb + 70, "Telemetry", "provider - model - latency - failures - fallback flag, per decision", yfb + 125, 11, 1160)
    label(x, 60, yfb + 190,
          "Used for: narrative text - candidate-mix hints - objective-weight suggestions - iteration choice.  Never used for: cost, revenue or profit figures.",
          ITAL, 26, GREY, "l")


P4_CARDS = [
    ("1", "Agent Request", "A request from one of the agents. It carries the agent's role, a prompt and the context.", BLUE),
    ("2", "LLM Client", "The single entry point for every language-model call. One record is kept per call.", YELLOW),
    ("3", "Provider Router", "Maps the role to a model, uses a cache, and has a circuit breaker with failover to another provider.", RED),
    ("4", "OpenRouter / Groq / Cerebras / Google", "The language-model providers that can answer a request.", GREEN),
    ("5", "Model Response", "The model's answer, either free text or structured JSON.", RED),
    ("6", "Validator", "Checks every answer against schema, range and consensus rules before it is used.", BLACK),
    ("7", "Use LLM output", "An accepted answer is used. The decision source is recorded as LLM.", BLACK),
    ("8", "Rule-based Fallback", "Used when the answer is rejected or the provider is unavailable: a deterministic template or score replaces the LLM.", BLACK),
    ("9", "Decision Applied", "The decision that enters the system. Its source, LLM or rule-based, is always recorded.", ORANGE),
    ("10", "Roles (top arrow)", "The agents that use the LLM: orchestrator, regional, service generator, coordinator and iteration selector.", INK),
    ("11", "Telemetry (bottom arrow)", "Per decision, the system records provider, model, latency, failures and whether the fallback was used.", INK),
]

PAGES = [
    ("AI Vessel Routing System - Hierarchical Multi-Agent Architecture",
     "Liner shipping network design: decomposition, regional search, one global network optimisation, independent verification",
     1450, page1, P1_CARDS),
    ("Regional Agent - Candidate Generation, Search and Allocation",
     "One instance per region, run in parallel; its results become candidates and hints for the global stage",
     1450, page2, P2_CARDS),
    ("Global Network Optimisation and Independent Verification",
     "One network over all demand: candidates are priced by one service model, solved, improved, and re-derived by a separate ledger",
     1160, page3, P3_CARDS),
    ("Agent and LLM Layer - Trust Boundary",
     "Language models advise and describe; every suggestion is validated, and the economic accounting never depends on them",
     1340, page4, P4_CARDS),
]

CARD_FONT, CARD_LEAD, COLS, GAP = 27, 35, 3, 30


def card_paragraph(title, text, width):
    st = ParagraphStyle("c", fontName=REG, fontSize=CARD_FONT, leading=CARD_LEAD, alignment=TA_LEFT, textColor=INK)
    stop = "" if title.endswith(("?", ".")) else "."
    p = Paragraph(f"<b>{esc(title)}{stop}</b> {esc(text)}", st)
    _, h = p.wrap(width, 10000)
    return p, h


def layout_cards(cards):
    colw = (W - 80 - GAP * (COLS - 1)) / COLS
    textw = colw - (100 if SHOW_NUMBERS else 56)
    rows, cur = [], []
    for i, cd in enumerate(cards):
        # without number badges the generators keep the letter they carry in the diagram ("A Direct services")
        title = cd[1] if SHOW_NUMBERS or not cd[0].isalpha() else f"{cd[0]}  {cd[1]}"
        p, h = card_paragraph(title, cd[2], textw)
        cur.append((cd, p, max(h + 34, 84)))
        if len(cur) == COLS or i == len(cards) - 1:
            rows.append(cur)
            cur = []
    return colw, rows, sum(max(r[2] for r in row) + GAP for row in rows)


def build(path):
    c = canvas.Canvas(path, pagesize=(W, 1000))
    c.setTitle("AI Vessel Routing System - System Architecture Diagram (large font, with block explanations)")
    for title, subtitle, dh, draw, cards in PAGES:
        colw, rows, cards_h = layout_cards(cards)
        y0 = 190
        H = int(y0 + dh + 50 + 70 + cards_h + 120)
        c.setPageSize((W, H))
        x = Ctx(c, H, y0)
        c.setFillColor(white)
        c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont(BOLD, 56)
        c.drawString(40, H - 72, title)
        c.setFillColor(GREY)
        c.setFont(ITAL, 30)
        c.drawString(40, H - 122, subtitle)
        draw(x)
        # explanation panel
        top = y0 + dh + 50
        c.setFillColor(INK)
        c.setFont(BOLD, 42)
        c.drawString(40, H - (top + 40), "What each block does")
        if SHOW_NUMBERS:
            c.setFillColor(GREY)
            c.setFont(ITAL, 26)
            c.drawString(560, H - (top + 40), "the numbers match the badges in the diagram above")
        ytop = top + 75
        for row in rows:
            rh = max(r[2] for r in row)
            for j, ((badge_lbl, ttl, txt, colr), p, _h) in enumerate(row):
                cx0 = 40 + j * (colw + GAP)
                c.setFillColor(CARD)
                c.setStrokeColor(CARD_LINE)
                c.setLineWidth(1.5)
                c.roundRect(cx0, H - (ytop + rh), colw, rh, 14, fill=1, stroke=1)
                c.setFillColor(colr)
                c.setStrokeColor(colr)
                c.roundRect(cx0, H - (ytop + rh), 14, rh, 6, fill=1, stroke=0)
                if SHOW_NUMBERS:
                    bx, by = cx0 + 52, H - (ytop + 26 + 14)
                    c.setFillColor(NAVY)
                    c.circle(bx, by, 24, fill=1, stroke=0)
                    c.setFillColor(white)
                    c.setFont(BOLD, 27 if len(badge_lbl) < 2 else 24)
                    c.drawCentredString(bx, by - 9, badge_lbl)
                p.drawOn(c, cx0 + (90 if SHOW_NUMBERS else 36), H - (ytop + 16) - p.height)
            ytop += rh + GAP
        # legend
        lx, ly = 40, H - (H - 60)
        c.setFont(REG, 26)
        for name, col in LEG:
            c.setFillColor(col)
            c.setStrokeColor(BLACK)
            c.setLineWidth(1.5)
            c.roundRect(lx, 38, 40, 28, 7, fill=1, stroke=1)
            c.setFillColor(INK)
            c.drawString(lx + 54, 44, name)
            lx += 54 + c.stringWidth(name, REG, 26) + 50
        c.showPage()
    c.save()


if __name__ == "__main__":
    from pathlib import Path
    default = Path(__file__).resolve().parents[1] / "docs" / "System_Architecture_Diagram_Large_Font.pdf"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    build(str(out))
    print(f"wrote {out}")
    print("\n".join(WARN) if WARN else "no text overflow detected")
