"""Generational design search.

A design is a set of genes (fields of sim.Design).  Each GENERATION opens new
genes (the generation's hypotheses), seeds its population with the previous
generation's elite, and runs a small genetic algorithm (tournament selection,
uniform crossover, mutation, elitism).  Afterwards every non-baseline gene in
the champion is ABLATED (reset to its baseline value) to measure its marginal
value: a hypothesis is CONFIRMED if its gene survives selection and removing it
costs > 0.5 % of annual cost, otherwise it is REFUTED and frozen at baseline
for later generations ("pruned").
"""
from __future__ import annotations

import copy
import random
from dataclasses import asdict, replace

from .sim import Design


class Evolver:
    def __init__(self, sim, seed=11, years_for=lambda d: 4 if d.bores else 1, fixed=None):
        self.sim = sim
        self.rng = random.Random(seed)
        self.cache = {}
        self.years_for = years_for
        self.space = {}          # gene -> allowed values
        self.baseline = {}       # gene -> baseline value
        self.frozen = dict(fixed or {})
        self.elite = [Design()]
        self.history = []

    def evaluate(self, d):
        k = d.key()
        if k not in self.cache:
            self.cache[k] = self.sim.run(d, years=self.years_for(d))
        return self.cache[k]

    def cost(self, d):
        return self.evaluate(d)["annual_cost"]

    def open_genes(self, genes):
        for g, (vals, base) in genes.items():
            self.space[g] = list(vals)
            self.baseline[g] = base

    def _random(self):
        d = copy.deepcopy(self.rng.choice(self.elite))
        for g, vals in self.space.items():
            if g in self.frozen:
                setattr(d, g, self.frozen[g])
            elif self.rng.random() < 0.5:
                setattr(d, g, self.rng.choice(vals))
        return d

    def _mutate(self, d, rate=0.18):
        d = copy.deepcopy(d)
        for g, vals in self.space.items():
            if g in self.frozen:
                setattr(d, g, self.frozen[g])
            elif self.rng.random() < rate:
                setattr(d, g, self.rng.choice(vals))
        return d

    def _cross(self, a, b):
        c = copy.deepcopy(a)
        for g in self.space:
            if self.rng.random() < 0.5:
                setattr(c, g, getattr(b, g))
        return c

    def run_generation(self, name, pop=28, iters=14, n_elite=6):
        population = [copy.deepcopy(e) for e in self.elite]
        for e in self.elite:  # each new gene tried on each elite
            for g in self.space:
                for v in self.space[g]:
                    if g not in self.frozen and v != getattr(e, g):
                        population.append(replace(e, **{g: v}))
        while len(population) < pop:
            population.append(self._random())
        trace = []
        for it in range(iters):
            scored = sorted(population, key=self.cost)
            trace.append([self.cost(scored[0]), sum(self.cost(x) for x in scored[:n_elite]) / n_elite])
            nxt = scored[:4]
            while len(nxt) < pop:
                p1 = min(self.rng.sample(scored[:pop], 3), key=self.cost)
                p2 = min(self.rng.sample(scored[:pop], 3), key=self.cost)
                nxt.append(self._mutate(self._cross(p1, p2)))
            population = nxt
        # local polish: one-gene coordinate descent on the champion
        best = min(population, key=self.cost)
        improved = True
        while improved:
            improved = False
            for g, vals in self.space.items():
                if g in self.frozen:
                    continue
                for v in vals:
                    c = replace(best, **{g: v})
                    if self.cost(c) < self.cost(best) - 1e-6:
                        best, improved = c, True
        ranked = sorted({x.key(): x for x in list(self.cache_designs())}.values(), key=self.cost)
        self.elite = ranked[:n_elite]
        ablation = {}
        for g in self.space:
            base = self.baseline[g]
            if getattr(best, g) != base:
                c = replace(best, **{g: base})
                ablation[g] = (self.cost(c) - self.cost(best)) / self.cost(best)
        rec = dict(name=name, best=asdict(best), result=self.evaluate(best), trace=trace, ablation=ablation,
                   evaluated=len(self.cache), top=[(asdict(x), self.evaluate(x)["annual_cost"]) for x in self.elite])
        self.history.append(rec)
        return rec

    def cache_designs(self):
        out = []
        for k in self.cache:
            out.append(Design(**dict(k)))
        return out

    def verdict(self, genes, rec, threshold=0.005):
        """Confirm/refute each gene of this generation; freeze refuted ones at baseline."""
        out = {}
        for g in genes:
            v = rec["best"][g]
            if v == self.baseline[g]:
                out[g] = ("refuted", 0.0)
                self.frozen[g] = self.baseline[g]
            else:
                gain = rec["ablation"].get(g, 0.0)
                if gain > threshold:
                    out[g] = ("confirmed", gain)
                else:
                    out[g] = ("marginal", gain)
        return out


def reoptimise(ev, start, fixed_gene, passes=3):
    """Coordinate descent over every open (non-frozen) gene except `fixed_gene`."""
    best = start
    for _ in range(passes):
        improved = False
        for g, vals in ev.space.items():
            if g == fixed_gene or g in ev.frozen:
                continue
            for v in vals:
                c = replace(best, **{g: v})
                if ev.cost(c) < ev.cost(best) - 1e-6:
                    best, improved = c, True
        if not improved:
            break
    return best


def paired_test(ev, champion, gene, threshold=0.005):
    """Fair hypothesis test: best design WITH the idea (each non-baseline value,
    everything else re-optimised) vs. best design WITHOUT it (baseline value,
    everything else re-optimised)."""
    base = ev.baseline[gene]
    off = reoptimise(ev, replace(champion, **{gene: base}), gene)
    ons = []
    for v in ev.space[gene]:
        if v == base:
            continue
        ons.append(reoptimise(ev, replace(champion, **{gene: v}), gene))
    on = min(ons, key=ev.cost) if ons else off
    c_on, c_off = ev.cost(on), ev.cost(off)
    rel = (c_off - c_on) / c_off            # +ve: the idea saves money
    status = "confirmed" if rel > threshold else ("refuted" if rel < -threshold else "marginal")
    return dict(status=status, saving_pct=rel * 100, cost_on=c_on, cost_off=c_off, best_on=asdict(on), best_off=asdict(off),
                value=str(getattr(on, gene))), (on if c_on < c_off else off)
