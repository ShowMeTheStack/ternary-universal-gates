//! Enumeration, universality testing, symmetry classification and
//! half-adder synthesis for binary-arity ternary gates.
//!
//! Conventions (match the paper): a gate g : T^2 -> T with T = {-,0,+}
//! is stored as [u8; 9] with entry i = 3*x + y holding g(x,y), trit values
//! 0,1,2 <-> -,0,+.  The integer label is sum_i g[i] * 3^i (entry 0 is the
//! units place), so label 451 is the appendix gate of the draft.
//!
//! All long subcommands are chunked and resumable: each chunk is written
//! atomically to <out>.parts/part_NNNNN.csv and skipped if already present;
//! the final file is assembled from the parts.
//!
//! Subcommands:
//!   enumerate  <out.csv>              E1: three independent universality tests, all 19683 gates
//!   orbits     <enum.csv> <out.json>  E2: S3xZ2 and Z2xZ2 orbit counts, Burnside check
//!   synth      <enum.csv> <out.csv>   E4: depth- and size-optimal h_sum/h_carry for every universal gate
//!   lowerbound <out.json>             E11: which gates (of all 19683) realise h_sum/h_carry at depth <= 2
//!   timing     <runs> <out.json>      E3: single-thread timing ablation of the universality tests

use std::collections::{HashMap, HashSet};
use std::fmt::Write as _;
use std::fs;
use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

const N: usize = 19683;
type Tab = [u8; 9];

fn decode(mut idx: u32) -> Tab {
    let mut t = [0u8; 9];
    for i in 0..9 {
        t[i] = (idx % 3) as u8;
        idx /= 3;
    }
    t
}

fn encode(t: &Tab) -> u32 {
    let mut v = 0u32;
    for i in (0..9).rev() {
        v = v * 3 + t[i] as u32;
    }
    v
}

#[inline(always)]
fn ap(g: &Tab, a: u8, b: u8) -> u8 {
    g[(3 * a + b) as usize]
}

#[inline(always)]
fn compose(g: &Tab, f: &Tab, h: &Tab) -> Tab {
    let mut out = [0u8; 9];
    for i in 0..9 {
        out[i] = ap(g, f[i], h[i]);
    }
    out
}

const PI1: Tab = [0, 0, 0, 1, 1, 1, 2, 2, 2];
const PI2: Tab = [0, 1, 2, 0, 1, 2, 0, 1, 2];

fn tab_str(t: &Tab) -> String {
    t.iter().map(|&v| ['-', '0', '+'][v as usize]).collect()
}

// ---------------------------------------------------------------- bitset

struct Bits {
    w: Vec<u64>,
    n: usize,
}
impl Bits {
    fn new(cap: usize) -> Self {
        Bits { w: vec![0; (cap + 63) / 64], n: 0 }
    }
    #[inline(always)]
    fn insert(&mut self, i: u32) -> bool {
        let (q, r) = ((i >> 6) as usize, i & 63);
        let m = 1u64 << r;
        if self.w[q] & m != 0 {
            false
        } else {
            self.w[q] |= m;
            self.n += 1;
            true
        }
    }
}

// ------------------------------------------------- test 1: full closure

/// Size of the binary part of Clone(g) (semi-naive fixpoint).  Universal
/// iff it equals 19683.  Returns (size, number of compositions performed).
fn full_closure(g: &Tab) -> (usize, u64) {
    let mut seen = Bits::new(N);
    let mut all: Vec<Tab> = Vec::new();
    let mut frontier: Vec<Tab> = Vec::new();
    for p in [PI1, PI2] {
        seen.insert(encode(&p));
        all.push(p);
        frontier.push(p);
    }
    let mut ops = 0u64;
    while !frontier.is_empty() && seen.n < N {
        let mut next = Vec::new();
        let old_len = all.len();
        for fi in 0..old_len {
            let f = all[fi];
            for h in &frontier {
                ops += 2;
                let a = compose(g, &f, h);
                if seen.insert(encode(&a)) {
                    next.push(a);
                }
                let b = compose(g, h, &f);
                if seen.insert(encode(&b)) {
                    next.push(b);
                }
            }
        }
        all.extend_from_slice(&next);
        frontier = next;
    }
    (seen.n, ops)
}

// ------------------------------------------------- test 2: unary closure

type Un = [u8; 3];
fn un_encode(u: &Un) -> u32 {
    u[0] as u32 + 3 * u[1] as u32 + 9 * u[2] as u32
}

/// Number of unary functions in Clone(g) (27 = unary complete).
fn unary_closure(g: &Tab) -> (usize, u64) {
    let id: Un = [0, 1, 2];
    let diag: Un = [ap(g, 0, 0), ap(g, 1, 1), ap(g, 2, 2)];
    let mut mask: u32 = 0;
    let mut all: Vec<Un> = Vec::new();
    let mut frontier: Vec<Un> = Vec::new();
    for u in [id, diag] {
        let e = un_encode(&u);
        if mask & (1 << e) == 0 {
            mask |= 1 << e;
            all.push(u);
            frontier.push(u);
        }
    }
    let mut ops = 0u64;
    while !frontier.is_empty() && mask.count_ones() < 27 {
        let mut next = Vec::new();
        let old_len = all.len();
        for fi in 0..old_len {
            let f = all[fi];
            for h in &frontier {
                ops += 2;
                for (p, q) in [(&f, h), (h, &f)] {
                    let u: Un = [ap(g, p[0], q[0]), ap(g, p[1], q[1]), ap(g, p[2], q[2])];
                    let e = un_encode(&u);
                    if mask & (1 << e) == 0 {
                        mask |= 1 << e;
                        next.push(u);
                    }
                }
            }
        }
        all.extend_from_slice(&next);
        frontier = next;
    }
    (mask.count_ones() as usize, ops)
}

// ------------------------------------------------- test 3: Rousseau

const PERMS: [[u8; 3]; 6] = [
    [0, 1, 2],
    [0, 2, 1],
    [1, 0, 2],
    [1, 2, 0],
    [2, 0, 1],
    [2, 1, 0],
];

fn has_proper_subalgebra(g: &Tab) -> bool {
    for m in 1u8..7 {
        let mut closed = true;
        'outer: for a in 0..3u8 {
            if m & (1 << a) == 0 {
                continue;
            }
            for b in 0..3u8 {
                if m & (1 << b) == 0 {
                    continue;
                }
                if m & (1 << ap(g, a, b)) == 0 {
                    closed = false;
                    break 'outer;
                }
            }
        }
        if closed {
            return true;
        }
    }
    false
}

fn is_automorphism(g: &Tab, s: &[u8; 3]) -> bool {
    (0..3u8).all(|a| (0..3u8).all(|b| s[ap(g, a, b) as usize] == ap(g, s[a as usize], s[b as usize])))
}

fn has_nontrivial_automorphism(g: &Tab) -> bool {
    PERMS[1..].iter().any(|s| is_automorphism(g, s))
}

fn has_nontrivial_congruence(g: &Tab) -> bool {
    for cls in [[0u8, 0, 1], [0, 1, 0], [0, 1, 1]] {
        let rel = |x: u8, y: u8| cls[x as usize] == cls[y as usize];
        let mut ok = true;
        for a1 in 0..3u8 {
            for a2 in 0..3u8 {
                if !rel(a1, a2) {
                    continue;
                }
                for b1 in 0..3u8 {
                    for b2 in 0..3u8 {
                        if rel(b1, b2) && !rel(ap(g, a1, b1), ap(g, a2, b2)) {
                            ok = false;
                        }
                    }
                }
            }
        }
        if ok {
            return true;
        }
    }
    false
}

/// Rousseau (1967): (T,g) primal iff no proper subalgebra, no nontrivial
/// automorphism, simple.
fn rousseau(g: &Tab) -> (bool, bool, bool) {
    (!has_proper_subalgebra(g), !has_nontrivial_automorphism(g), !has_nontrivial_congruence(g))
}

// ------------------------------------------------- structural properties

fn surjective(g: &Tab) -> bool {
    let mut m = 0u8;
    for v in g {
        m |= 1 << v;
    }
    m == 7
}
fn commutative(g: &Tab) -> bool {
    (0..3u8).all(|a| (0..3u8).all(|b| ap(g, a, b) == ap(g, b, a)))
}
fn self_dual(g: &Tab) -> bool {
    is_automorphism(g, &PERMS[5])
}
fn inc_invariant(g: &Tab) -> bool {
    is_automorphism(g, &PERMS[3]) // x -> x+1 mod 3  (0,1,2) -> (1,2,0)
}
fn zero_preserving(g: &Tab) -> bool {
    ap(g, 1, 1) == 1
}
fn fixed_points_diag(g: &Tab) -> u8 {
    (0..3u8).filter(|&c| ap(g, c, c) == c).count() as u8
}
fn diag_is_bijective(g: &Tab) -> bool {
    let d = [ap(g, 0, 0), ap(g, 1, 1), ap(g, 2, 2)];
    d[0] != d[1] && d[1] != d[2] && d[0] != d[2]
}
fn essential_arity(g: &Tab) -> u8 {
    let dep_x = (0..3u8).any(|y| (0..3u8).any(|x1| (0..3u8).any(|x2| ap(g, x1, y) != ap(g, x2, y))));
    let dep_y = (0..3u8).any(|x| (0..3u8).any(|y1| (0..3u8).any(|y2| ap(g, x, y1) != ap(g, x, y2))));
    dep_x as u8 + dep_y as u8
}

// ------------------------------------------------- symmetry

/// (sigma, swap) . g  (x,y) = sigma( g( sigma^-1 x', sigma^-1 y' ) ), (x',y') = (y,x) if swap
fn act(g: &Tab, s: &[u8; 3], swap: bool) -> Tab {
    let mut inv = [0u8; 3];
    for i in 0..3 {
        inv[s[i] as usize] = i as u8;
    }
    let mut out = [0u8; 9];
    for x in 0..3u8 {
        for y in 0..3u8 {
            let (xx, yy) = if swap { (y, x) } else { (x, y) };
            out[(3 * x + y) as usize] = s[ap(g, inv[xx as usize], inv[yy as usize]) as usize];
        }
    }
    out
}

fn canon12(g: &Tab) -> u32 {
    let mut best = u32::MAX;
    for s in &PERMS {
        for sw in [false, true] {
            best = best.min(encode(&act(g, s, sw)));
        }
    }
    best
}

/// Z2 x Z2 = {id, negation} x {noswap, swap}: the subgroup fixing h_sum and h_carry.
fn canon4(g: &Tab) -> u32 {
    let mut best = u32::MAX;
    for s in [&PERMS[0], &PERMS[5]] {
        for sw in [false, true] {
            best = best.min(encode(&act(g, s, sw)));
        }
    }
    best
}

// ------------------------------------------------- targets

fn h_sum() -> Tab {
    let mut t = [0u8; 9];
    for x in 0..3i8 {
        for y in 0..3i8 {
            let mut s = (x - 1) + (y - 1);
            if s > 1 {
                s -= 3;
            }
            if s < -1 {
                s += 3;
            }
            t[(3 * x + y) as usize] = (s + 1) as u8;
        }
    }
    t
}
fn h_carry() -> Tab {
    let mut t = [0u8; 9];
    for x in 0..3i8 {
        for y in 0..3i8 {
            let s = (x - 1) + (y - 1);
            let c = if s == 2 { 1 } else if s == -2 { -1 } else { 0 };
            t[(3 * x + y) as usize] = (c + 1) as u8;
        }
    }
    t
}

// ------------------------------------------------- synthesis (paper's Alg. 3 and 4)

#[derive(Clone, Copy)]
struct Node {
    gc: u32,
    parents: Option<(u32, u32)>,
}

fn expr(tt: u32, nodes: &HashMap<u32, Node>, out: &mut String) {
    if tt == encode(&PI1) {
        out.push('x');
        return;
    }
    if tt == encode(&PI2) {
        out.push('y');
        return;
    }
    let (f, h) = nodes[&tt].parents.expect("non-projection must have parents");
    out.push_str("G(");
    expr(f, nodes, out);
    out.push(',');
    expr(h, nodes, out);
    out.push(')');
}

/// BFS by depth, tree-model gate count. Returns (gate_count, depth, expression).
fn depth_optimal(g: &Tab, target: &Tab, max_depth: u32) -> Option<(u32, u32, String)> {
    let tgt = encode(target);
    let mut nodes: HashMap<u32, Node> = HashMap::new();
    let mut all: Vec<u32> = Vec::new();
    let mut prev: Vec<u32> = Vec::new();
    for p in [PI1, PI2] {
        let e = encode(&p);
        nodes.insert(e, Node { gc: 0, parents: None });
        all.push(e);
        prev.push(e);
    }
    if nodes.contains_key(&tgt) {
        return Some((0, 0, String::new()));
    }
    for d in 1..=max_depth {
        let mut best: HashMap<u32, (u32, (u32, u32))> = HashMap::new();
        for &f in &all {
            let ft = decode(f);
            let fgc = nodes[&f].gc;
            for &h in &prev {
                let ht = decode(h);
                let gc = fgc + nodes[&h].gc + 1;
                for (a, b, at, bt) in [(f, h, &ft, &ht), (h, f, &ht, &ft)] {
                    let r = encode(&compose(g, at, bt));
                    let e = best.entry(r).or_insert((u32::MAX, (0, 0)));
                    if gc < e.0 {
                        *e = (gc, (a, b));
                    }
                }
            }
        }
        let mut layer = Vec::new();
        let mut found = None;
        for (r, (gc, par)) in best {
            if !nodes.contains_key(&r) {
                nodes.insert(r, Node { gc, parents: Some(par) });
                layer.push(r);
            }
            if r == tgt {
                let mut s = String::new();
                expr(r, &nodes, &mut s);
                found = Some((nodes[&r].gc, d, s));
            }
        }
        if found.is_some() {
            return found;
        }
        all.extend_from_slice(&layer);
        prev = layer;
        if prev.is_empty() {
            break;
        }
    }
    None
}

/// DP by size, DAG model. Returns (size, depth).
fn size_optimal(g: &Tab, target: &Tab, max_size: u32) -> Option<(u32, u32)> {
    let tgt = encode(target);
    let mut known: HashMap<u32, (u32, u32)> = HashMap::new();
    let mut by_size: Vec<Vec<u32>> = vec![Vec::new()];
    for p in [PI1, PI2] {
        let e = encode(&p);
        known.insert(e, (0, 0));
        by_size[0].push(e);
    }
    if known.contains_key(&tgt) {
        return Some((0, 0));
    }
    for s in 1..=max_size {
        let mut new_items = Vec::new();
        for sf in 0..s {
            let sg = s - 1 - sf;
            if by_size[sf as usize].is_empty() || by_size[sg as usize].is_empty() {
                continue;
            }
            for &f in &by_size[sf as usize] {
                let ft = decode(f);
                let fd = known[&f].1;
                for &h in &by_size[sg as usize] {
                    let ht = decode(h);
                    let r = encode(&compose(g, &ft, &ht));
                    if !known.contains_key(&r) {
                        let d = fd.max(known[&h].1) + 1;
                        known.insert(r, (s, d));
                        new_items.push(r);
                        if r == tgt {
                            return Some((s, d));
                        }
                    }
                }
            }
        }
        by_size.push(new_items);
    }
    None
}

// ------------------------------------------------- resumable chunked runner

fn atomic_write(path: &str, content: &str) {
    let tmp = format!("{}.tmp", path);
    fs::write(&tmp, content).expect("write tmp");
    fs::rename(&tmp, path).expect("rename");
}

/// Process `items` in chunks across all cores; each chunk's CSV lines go to
/// `<out>.parts/part_NNNNN.csv` (skipped if present); finally assemble `<out>`.
fn chunked_csv<T: Sync>(items: &[T], chunk: usize, out: &str, header: &str, f: impl Fn(&T) -> String + Sync) {
    let parts_dir = format!("{}.parts", out);
    fs::create_dir_all(&parts_dir).unwrap();
    let n_chunks = (items.len() + chunk - 1) / chunk;
    let next = AtomicUsize::new(0);
    let done = AtomicUsize::new(0);
    let threads = std::thread::available_parallelism().map(|x| x.get()).unwrap_or(8);
    let t0 = Instant::now();
    std::thread::scope(|sc| {
        for _ in 0..threads {
            sc.spawn(|| loop {
                let k = next.fetch_add(1, Ordering::Relaxed);
                if k >= n_chunks {
                    break;
                }
                let path = format!("{}/part_{:05}.csv", parts_dir, k);
                if Path::new(&path).exists() {
                    continue;
                }
                let lo = k * chunk;
                let hi = ((k + 1) * chunk).min(items.len());
                let mut s = String::new();
                for it in &items[lo..hi] {
                    s.push_str(&f(it));
                    s.push('\n');
                }
                atomic_write(&path, &s);
                let d = done.fetch_add(1, Ordering::Relaxed) + 1;
                if d % 8 == 0 || d == n_chunks {
                    eprintln!("  [{:>6.1}s] chunk {}/{} done", t0.elapsed().as_secs_f64(), d, n_chunks);
                }
            });
        }
    });
    let mut s = String::from(header);
    s.push('\n');
    for k in 0..n_chunks {
        let path = format!("{}/part_{:05}.csv", parts_dir, k);
        s.push_str(&fs::read_to_string(&path).expect("part missing"));
    }
    atomic_write(out, &s);
}

// ------------------------------------------------- CSV helpers

fn read_universal(path: &str) -> Vec<u32> {
    let s = fs::read_to_string(path).expect("read csv");
    let mut out = Vec::new();
    for (i, line) in s.lines().enumerate() {
        if i == 0 {
            continue;
        }
        let cols: Vec<&str> = line.split(',').collect();
        // gate,closure_size,unary_size,rousseau,...
        if cols[1] == "19683" {
            out.push(cols[0].parse().unwrap());
        }
    }
    out
}

// ------------------------------------------------- subcommands

fn cmd_enumerate(out: &str) {
    let t0 = Instant::now();
    let items: Vec<u32> = (0..N as u32).collect();
    let header = "gate,closure_size,unary_size,rousseau,no_subalg,no_autom,simple,closure_ops,unary_ops,surjective,commutative,self_dual,inc_invariant,zero_preserving,diag_fixed_points,diag_bijective,essential_arity,canon12,canon4,table";
    chunked_csv(&items, 128, out, header, |&i| {
        let g = decode(i);
        let (cs, cops) = full_closure(&g);
        let (us, uops) = unary_closure(&g);
        let (nosub, noaut, simple) = rousseau(&g);
        format!(
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
            i, cs, us, (nosub && noaut && simple) as u8, nosub as u8, noaut as u8, simple as u8, cops, uops,
            surjective(&g) as u8, commutative(&g) as u8, self_dual(&g) as u8, inc_invariant(&g) as u8,
            zero_preserving(&g) as u8, fixed_points_diag(&g), diag_is_bijective(&g) as u8, essential_arity(&g),
            canon12(&g), canon4(&g), tab_str(&g)
        )
    });
    // summary
    let s = fs::read_to_string(out).unwrap();
    let (mut n_full, mut n_un, mut n_r, mut agree, mut tot_ops) = (0u32, 0u32, 0u32, 0u32, 0u64);
    for line in s.lines().skip(1) {
        let c: Vec<&str> = line.split(',').collect();
        let f = c[1] == "19683";
        let u = c[2] == "27";
        let r = c[3] == "1";
        n_full += f as u32;
        n_un += u as u32;
        n_r += r as u32;
        agree += (f == u && u == r) as u32;
        tot_ops += c[7].parse::<u64>().unwrap();
    }
    println!("enumerate: {} gates in {:.1}s", N, t0.elapsed().as_secs_f64());
    println!("  universal by full closure : {}", n_full);
    println!("  universal by unary closure: {}", n_un);
    println!("  universal by Rousseau     : {}", n_r);
    println!("  all three agree on        : {} / {}", agree, N);
    println!("  total closure compositions: {}", tot_ops);
}

fn cmd_orbits(inp: &str, out: &str) {
    let univ = read_universal(inp);
    let mut is_univ = vec![false; N];
    for &u in &univ {
        is_univ[u as usize] = true;
    }
    let mut invariant = true;
    for &u in &univ {
        let g = decode(u);
        for s in &PERMS {
            for sw in [false, true] {
                if !is_univ[encode(&act(&g, s, sw)) as usize] {
                    invariant = false;
                }
            }
        }
    }
    let mut c12_all = HashSet::new();
    let mut c12_u = HashSet::new();
    let mut c4_u = HashSet::new();
    let mut c4_all = HashSet::new();
    let mut size12: HashMap<u32, u32> = HashMap::new();
    for i in 0..N as u32 {
        let g = decode(i);
        let c = canon12(&g);
        let c4 = canon4(&g);
        c12_all.insert(c);
        c4_all.insert(c4);
        if is_univ[i as usize] {
            c12_u.insert(c);
            c4_u.insert(c4);
            *size12.entry(c).or_insert(0) += 1;
        }
    }
    let mut size_hist: HashMap<u32, u32> = HashMap::new();
    for n in size12.values() {
        *size_hist.entry(*n).or_insert(0) += 1;
    }
    let mut fix_all = 0u64;
    let mut fix_u = 0u64;
    let mut fix_detail = Vec::new();
    for s in &PERMS {
        for sw in [false, true] {
            let (mut fa, mut fu) = (0u64, 0u64);
            for i in 0..N as u32 {
                if encode(&act(&decode(i), s, sw)) == i {
                    fa += 1;
                    if is_univ[i as usize] {
                        fu += 1;
                    }
                }
            }
            fix_detail.push(format!("{{\"perm\":{:?},\"swap\":{},\"fix_all\":{},\"fix_univ\":{}}}", s, sw, fa, fu));
            fix_all += fa;
            fix_u += fu;
        }
    }
    // Burnside for Z2xZ2 on universal set
    let mut fix4_u = 0u64;
    for s in [&PERMS[0], &PERMS[5]] {
        for sw in [false, true] {
            for &u in &univ {
                if encode(&act(&decode(u), s, sw)) == u {
                    fix4_u += 1;
                }
            }
        }
    }
    let mut sh: Vec<_> = size_hist.into_iter().collect();
    sh.sort();
    let j = format!(
        "{{\n  \"universal\": {},\n  \"image_of_universal_is_universal\": {},\n  \"orbits12_all\": {},\n  \"orbits12_universal\": {},\n  \"orbits4_all\": {},\n  \"orbits4_universal\": {},\n  \"burnside_sum_all\": {},\n  \"burnside_orbits_all\": {},\n  \"burnside_sum_univ\": {},\n  \"burnside_orbits_univ\": {},\n  \"burnside4_sum_univ\": {},\n  \"burnside4_orbits_univ\": {},\n  \"class_size_hist_univ\": [{}],\n  \"fix\": [{}]\n}}\n",
        univ.len(), invariant, c12_all.len(), c12_u.len(), c4_all.len(), c4_u.len(),
        fix_all, fix_all as f64 / 12.0, fix_u, fix_u as f64 / 12.0, fix4_u, fix4_u as f64 / 4.0,
        sh.iter().map(|(a, b)| format!("[{},{}]", a, b)).collect::<Vec<_>>().join(","), fix_detail.join(",")
    );
    atomic_write(out, &j);
    print!("{}", j);
}

fn cmd_synth(inp: &str, out: &str) {
    let univ = read_universal(inp);
    let hs = h_sum();
    let hc = h_carry();
    println!("h_sum   = {}  (label {})", tab_str(&hs), encode(&hs));
    println!("h_carry = {}  (label {})", tab_str(&hc), encode(&hc));
    let t0 = Instant::now();
    let header = "gate,canon12,canon4,commutative,Ds,Gs_tree,Dc,Gc_tree,DFA_carry,GFA_tree,Gs_dag,ds_dag,Gc_dag,dc_dag,GFA_dag,expr_sum,expr_carry";
    chunked_csv(&univ, 64, out, header, |&i| {
        let g = decode(i);
        let ds = depth_optimal(&g, &hs, 10);
        let dc = depth_optimal(&g, &hc, 10);
        let ss = size_optimal(&g, &hs, 10);
        let sc = size_optimal(&g, &hc, 10);
        // per-field output: a failed sub-search leaves its fields empty instead of blanking the row
        let o = |v: Option<u32>| v.map(|x| x.to_string()).unwrap_or_default();
        let (d_s, gs, es) = ds.map(|(g, d, e)| (Some(d), Some(g), e)).unwrap_or((None, None, String::new()));
        let (d_c, gc, ec) = dc.map(|(g, d, e)| (Some(d), Some(g), e)).unwrap_or((None, None, String::new()));
        let (gsd, dsd) = ss.map(|(a, b)| (Some(a), Some(b))).unwrap_or((None, None));
        let (gcd, dcd) = sc.map(|(a, b)| (Some(a), Some(b))).unwrap_or((None, None));
        let dfa = match (d_s, d_c) { (Some(a), Some(b)) => Some(2 * a + b), _ => None };
        let gfa_t = match (gs, gc) { (Some(a), Some(b)) => Some(3 * a + 2 * b), _ => None };
        let gfa_d = match (gsd, gcd) { (Some(a), Some(b)) => Some(3 * a + 2 * b), _ => None };
        format!(
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},\"{}\",\"{}\"",
            i, canon12(&g), canon4(&g), commutative(&g) as u8,
            o(d_s), o(gs), o(d_c), o(gc), o(dfa), o(gfa_t), o(gsd), o(dsd), o(gcd), o(dcd), o(gfa_d), es, ec
        )
    });
    println!("synth: {} gates in {:.1}s", univ.len(), t0.elapsed().as_secs_f64());
}

/// E11: for every gate (universal or not), can h_sum / h_carry be realised at depth <= 2?
/// depth 1: G(a,b), a,b in {x,y}. depth 2: G(u,v) with u,v in {x,y} U {G(a,b)}.
fn cmd_lowerbound(out: &str) {
    let hs = encode(&h_sum());
    let hc = encode(&h_carry());
    let mut d1s = Vec::new();
    let mut d1c = Vec::new();
    let mut d2s = Vec::new();
    let mut d2c = Vec::new();
    for i in 0..N as u32 {
        let g = decode(i);
        let base = [PI1, PI2];
        let mut lvl1: Vec<Tab> = Vec::new();
        for a in &base {
            for b in &base {
                lvl1.push(compose(&g, a, b));
            }
        }
        if lvl1.iter().any(|t| encode(t) == hs) {
            d1s.push(i);
        }
        if lvl1.iter().any(|t| encode(t) == hc) {
            d1c.push(i);
        }
        let mut pool: Vec<Tab> = base.to_vec();
        pool.extend(lvl1.iter().cloned());
        let (mut fs_, mut fc) = (false, false);
        for u in &pool {
            for v in &pool {
                let e = encode(&compose(&g, u, v));
                fs_ |= e == hs;
                fc |= e == hc;
            }
        }
        if fs_ {
            d2s.push(i);
        }
        if fc {
            d2c.push(i);
        }
    }
    let j = format!(
        "{{\n  \"h_sum_depth1_gates\": {:?},\n  \"h_carry_depth1_gates\": {:?},\n  \"h_sum_depth_le2_gates\": {:?},\n  \"h_carry_depth_le2_gates\": {:?},\n  \"n_h_sum_depth_le2\": {},\n  \"n_h_carry_depth_le2\": {}\n}}\n",
        d1s, d1c, d2s, d2c, d2s.len(), d2c.len()
    );
    atomic_write(out, &j);
    print!("{}", j);
}

fn median(v: &[f64]) -> f64 {
    let mut w = v.to_vec();
    w.sort_by(|a, b| a.partial_cmp(b).unwrap());
    w[w.len() / 2]
}

fn cmd_timing(runs: usize, out: &str) {
    let mut reps: Vec<u32> = Vec::new();
    {
        let mut seen = HashSet::new();
        for i in 0..N as u32 {
            if seen.insert(canon12(&decode(i))) {
                reps.push(i);
            }
        }
    }
    let all: Vec<u32> = (0..N as u32).collect();
    let mut report = Vec::new();
    let methods: Vec<(&str, &Vec<u32>, Box<dyn Fn(&Tab) -> (bool, u64)>)> = vec![
        ("unary_all", &all, Box::new(|g| { let (n, o) = unary_closure(g); (n == 27, o) })),
        ("unary_reps", &reps, Box::new(|g| { let (n, o) = unary_closure(g); (n == 27, o) })),
        ("rousseau_all", &all, Box::new(|g| { let (a, b, c) = rousseau(g); (a && b && c, 14) })),
        ("rousseau_reps", &reps, Box::new(|g| { let (a, b, c) = rousseau(g); (a && b && c, 14) })),
    ];
    for (name, set, f) in &methods {
        let mut times = Vec::new();
        let (mut count, mut ops) = (0usize, 0u64);
        for _ in 0..runs {
            let t = Instant::now();
            count = 0;
            ops = 0;
            for &i in set.iter() {
                let (u, o) = f(&decode(i));
                count += u as usize;
                ops += o;
            }
            times.push(t.elapsed().as_secs_f64());
        }
        let (med, min, max) = (median(&times), times.iter().cloned().fold(f64::MAX, f64::min), times.iter().cloned().fold(0.0, f64::max));
        println!("{:14} n={:5} universal={:5} ops={:9} median={:.4}s min={:.4}s max={:.4}s", name, set.len(), count, ops, med, min, max);
        report.push(format!("{{\"method\":\"{}\",\"n_gates\":{},\"universal_found\":{},\"ops\":{},\"runs\":{},\"median_s\":{},\"min_s\":{},\"max_s\":{}}}", name, set.len(), count, ops, runs, med, min, max));
    }
    let mut times = Vec::new();
    for _ in 0..runs {
        let t = Instant::now();
        let mut seen = HashSet::new();
        for i in 0..N as u32 {
            seen.insert(canon12(&decode(i)));
        }
        times.push(t.elapsed().as_secs_f64());
    }
    println!("{:14} median={:.4}s", "canonicalise", median(&times));
    report.push(format!("{{\"method\":\"canonicalise_all\",\"n_gates\":{},\"runs\":{},\"median_s\":{}}}", N, runs, median(&times)));
    // full closure, single thread, on the universal reps and on a sample of non-universal reps
    let mut per_gate = Vec::new();
    for &i in &reps {
        let g = decode(i);
        let t = Instant::now();
        let (n, o) = full_closure(&g);
        per_gate.push((i, n == N, o, t.elapsed().as_secs_f64()));
    }
    let u_times: Vec<f64> = per_gate.iter().filter(|p| p.1).map(|p| p.3).collect();
    let n_times: Vec<f64> = per_gate.iter().filter(|p| !p.1).map(|p| p.3).collect();
    let u_ops: u64 = per_gate.iter().filter(|p| p.1).map(|p| p.2).sum();
    let n_ops: u64 = per_gate.iter().filter(|p| !p.1).map(|p| p.2).sum();
    println!("closure_reps   universal: n={} median={:.4}s total={:.2}s ops={}", u_times.len(), median(&u_times), u_times.iter().sum::<f64>(), u_ops);
    println!("closure_reps   non-univ : n={} median={:.4}s total={:.2}s ops={}", n_times.len(), median(&n_times), n_times.iter().sum::<f64>(), n_ops);
    report.push(format!("{{\"method\":\"full_closure_reps\",\"n_universal\":{},\"median_s_universal\":{},\"total_s_universal\":{},\"ops_universal\":{},\"n_nonuniversal\":{},\"median_s_nonuniversal\":{},\"total_s_nonuniversal\":{},\"ops_nonuniversal\":{}}}",
        u_times.len(), median(&u_times), u_times.iter().sum::<f64>(), u_ops, n_times.len(), median(&n_times), n_times.iter().sum::<f64>(), n_ops));
    atomic_write(out, &format!("[\n{}\n]\n", report.join(",\n")));
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    match a.get(1).map(|s| s.as_str()) {
        Some("enumerate") => cmd_enumerate(&a[2]),
        Some("orbits") => cmd_orbits(&a[2], &a[3]),
        Some("synth") => cmd_synth(&a[2], &a[3]),
        Some("lowerbound") => cmd_lowerbound(&a[2]),
        Some("timing") => cmd_timing(a[2].parse().unwrap(), &a[3]),
        Some("k4") => k4::run(&a[2]),
        _ => {
            eprintln!("usage: univ enumerate <out.csv> | orbits <enum.csv> <out.json> | synth <enum.csv> <out.csv> | lowerbound <out.json> | timing <runs> <out.json> | k4 <out_dir>");
            std::process::exit(2);
        }
    }
}

// ================================================================== k = 4 (E12)
// Two-input gates on 4 values: 4^16 = 4,294,967,296 gates. Universality by the
// Rousseau–Schofield criterion in Davies's form: no proper closed subset, no nontrivial
// invariant equivalence relation, no preserved permutation consisting of n/p disjoint
// cycles of the same prime length p (for n = 4: the three fixed-point-free involutions).
// Cell i = 4*x + y holds g(x,y) = (idx >> 2i) & 3. Resumable: 4096 ranges of 2^20 gates,
// one small result file per range. Orbits under S4 x Z2 via Burnside: fixed gates of each
// non-identity group element are enumerated directly (few), identity contributes T(4).

mod k4 {
    use super::atomic_write;
    use std::fs;
    use std::path::Path;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::time::Instant;

    pub const K: usize = 4;
    #[inline(always)]
    fn ap(g: u32, a: u32, b: u32) -> u32 { (g >> (2 * (4 * a + b))) & 3 }

    // --- condition (a): no proper nonempty closed subset (14 masks)
    #[inline(always)]
    fn has_closed_subset(g: u32) -> bool {
        // singletons first (cheap, kills ~68%)
        for a in 0..4u32 { if ap(g, a, a) == a { return true; } }
        for m in 1u32..15 {
            if m.count_ones() < 2 { continue; }
            let mut closed = true;
            'o: for a in 0..4u32 {
                if m & (1 << a) == 0 { continue; }
                for b in 0..4u32 {
                    if m & (1 << b) == 0 { continue; }
                    if m & (1 << ap(g, a, b)) == 0 { closed = false; break 'o; }
                }
            }
            if closed { return true; }
        }
        false
    }
    // --- condition (b): no nontrivial invariant equivalence relation (13 partitions of a 4-set)
    const PARTS: [[u8; 4]; 13] = [
        [0,0,1,2],[0,1,0,2],[0,1,2,0],[0,1,1,2],[0,1,2,1],[0,1,2,2], // one pair + two singletons
        [0,0,1,1],[0,1,0,1],[0,1,1,0],                               // two pairs
        [0,0,0,1],[0,0,1,0],[0,1,0,0],[0,1,1,1],                     // triple + singleton
    ];
    #[inline(always)]
    fn has_congruence(g: u32) -> bool {
        for cls in PARTS.iter() {
            let mut ok = true;
            'o: for a1 in 0..4u32 { for a2 in 0..4u32 {
                if cls[a1 as usize] != cls[a2 as usize] { continue; }
                for b1 in 0..4u32 { for b2 in 0..4u32 {
                    if cls[b1 as usize] != cls[b2 as usize] { continue; }
                    if cls[ap(g, a1, b1) as usize] != cls[ap(g, a2, b2) as usize] { ok = false; break 'o; }
                }}
            }}
            if ok { return true; }
        }
        false
    }
    // --- condition (c): no preserved fixed-point-free involution (all cycles length 2)
    const INV: [[u32; 4]; 3] = [[1,0,3,2],[2,3,0,1],[3,2,1,0]];
    #[inline(always)]
    fn preserves_involution(g: u32) -> bool {
        for s in INV.iter() {
            let mut ok = true;
            'o: for a in 0..4u32 { for b in 0..4u32 {
                if s[ap(g, a, b) as usize] != ap(g, s[a as usize], s[b as usize]) { ok = false; break 'o; }
            }}
            if ok { return true; }
        }
        false
    }
    #[inline(always)]
    pub fn universal(g: u32) -> bool {
        !has_closed_subset(g) && !has_congruence(g) && !preserves_involution(g)
    }
    // full automorphism test (24 perms) — for a Rousseau-form cross-check on a sample
    fn perms() -> Vec<[u32; 4]> {
        let mut v = Vec::new();
        for a in 0..4u32 { for b in 0..4u32 { for c in 0..4u32 { for d in 0..4u32 {
            if a != b && a != c && a != d && b != c && b != d && c != d { v.push([a, b, c, d]); }
        }}}}
        v
    }
    fn is_auto(g: u32, s: &[u32; 4]) -> bool {
        (0..4u32).all(|a| (0..4u32).all(|b| s[ap(g, a, b) as usize] == ap(g, s[a as usize], s[b as usize])))
    }

    pub fn act(g: u32, s: &[u32; 4], swap: bool) -> u32 {
        let mut inv = [0u32; 4];
        for i in 0..4 { inv[s[i] as usize] = i as u32; }
        let mut out = 0u32;
        for x in 0..4u32 { for y in 0..4u32 {
            let (xx, yy) = if swap { (y, x) } else { (x, y) };
            let v = s[ap(g, inv[xx as usize], inv[yy as usize]) as usize];
            out |= v << (2 * (4 * x + y));
        }}
        out
    }

    /// Enumerate all gates fixed by (s, swap) and count how many are universal.
    /// Fixed iff g(x,y) = s[g(psi(x,y))] with psi(x,y) = (inv x', inv y'); values along each
    /// psi-cycle are determined by one free value v with s^L(v) = v.
    fn fixed_gates(s: &[u32; 4], swap: bool) -> (u64, u64) {
        let mut inv = [0u32; 4];
        for i in 0..4 { inv[s[i] as usize] = i as u32; }
        let psi = |c: u32| -> u32 { let (x, y) = (c / 4, c % 4); let (xx, yy) = if swap { (y, x) } else { (x, y) }; 4 * inv[xx as usize] + inv[yy as usize] };
        // cycles of psi over the 16 cells
        let mut seen = [false; 16];
        let mut cycles: Vec<Vec<u32>> = Vec::new();
        for c0 in 0..16u32 {
            if seen[c0 as usize] { continue; }
            let mut cyc = vec![]; let mut c = c0;
            while !seen[c as usize] { seen[c as usize] = true; cyc.push(c); c = psi(c); }
            cycles.push(cyc);
        }
        // along a cycle c0 -> psi(c0) -> ..., g(c) = s[g(psi(c))] so g(psi(c)) = inv[g(c)]
        let mut total = 0u64; let mut univ = 0u64;
        let mut choice = vec![0u32; cycles.len()];
        let ncyc = cycles.len();
        // iterate over all assignments of free values (4^ncyc, with consistency filter)
        let limit = 1u64 << (2 * ncyc);
        for code in 0..limit {
            let mut ok = true; let mut g = 0u32;
            for (ci, cyc) in cycles.iter().enumerate() {
                let v = ((code >> (2 * ci)) & 3) as u32;
                choice[ci] = v;
                let mut cur = v;
                for &c in cyc.iter() { g |= cur << (2 * c); cur = inv[cur as usize]; }
                if cur != v { ok = false; break; } // s^L(v) != v
            }
            if !ok { continue; }
            total += 1;
            if universal(g) { univ += 1; }
        }
        (total, univ)
    }

    pub fn run(out_dir: &str) {
        fs::create_dir_all(out_dir).unwrap();
        let n_ranges: u64 = 4096; let per: u64 = 1u64 << 20; // 4096 x 2^20 = 2^32
        let next = AtomicUsize::new(0); let done = AtomicUsize::new(0);
        let threads = std::thread::available_parallelism().map(|x| x.get()).unwrap_or(8);
        let t0 = Instant::now();
        std::thread::scope(|sc| {
            for _ in 0..threads {
                sc.spawn(|| loop {
                    let r = next.fetch_add(1, Ordering::Relaxed) as u64;
                    if r >= n_ranges { break; }
                    let path = format!("{}/part_{:04}.txt", out_dir, r);
                    if Path::new(&path).exists() { continue; }
                    let (mut nu, mut n_sub, mut n_cong, mut n_inv) = (0u64, 0u64, 0u64, 0u64);
                    let mut diag_fpf_univ = [0u64; 4]; // universal count by number of ... (unused slot) 
                    let mut by_diag_bij = 0u64;
                    for g in (r * per)..((r + 1) * per) {
                        let g = g as u32;
                        let a = has_closed_subset(g);
                        if a { n_sub += 1; continue; }
                        let b = has_congruence(g);
                        if b { n_cong += 1; continue; }
                        let c = preserves_involution(g);
                        if c { n_inv += 1; continue; }
                        nu += 1;
                        let d = [ap(g,0,0), ap(g,1,1), ap(g,2,2), ap(g,3,3)];
                        let bij = d[0]!=d[1] && d[0]!=d[2] && d[0]!=d[3] && d[1]!=d[2] && d[1]!=d[3] && d[2]!=d[3];
                        if bij { by_diag_bij += 1; }
                        let _ = &mut diag_fpf_univ;
                    }
                    atomic_write(&path, &format!("{} {} {} {} {}\n", nu, n_sub, n_cong, n_inv, by_diag_bij));
                    let d = done.fetch_add(1, Ordering::Relaxed) + 1;
                    if d % 64 == 0 { eprintln!("  [{:>7.1}s] k4 range {}/{} done", t0.elapsed().as_secs_f64(), d, n_ranges); }
                });
            }
        });
        // assemble
        let (mut nu, mut n_sub, mut n_cong, mut n_inv, mut bij) = (0u64, 0u64, 0u64, 0u64, 0u64);
        for r in 0..n_ranges {
            let s = fs::read_to_string(format!("{}/part_{:04}.txt", out_dir, r)).expect("part");
            let v: Vec<u64> = s.split_whitespace().map(|x| x.parse().unwrap()).collect();
            nu += v[0]; n_sub += v[1]; n_cong += v[2]; n_inv += v[3]; bij += v[4];
        }
        // Burnside over S4 x Z2 (48 elements): identity contributes (4^16, T(4))
        let mut fix_all = 1u64 << 32; let mut fix_u = nu; let mut detail = Vec::new();
        for s in perms().iter() {
            for sw in [false, true] {
                if *s == [0,1,2,3] && !sw { continue; }
                let (t, u) = fixed_gates(s, sw);
                fix_all += t; fix_u += u;
                detail.push(format!("{{\"perm\":{:?},\"swap\":{},\"fix_all\":{},\"fix_univ\":{}}}", s, sw, t, u));
            }
        }
        // sample cross-check: Davies form vs full Rousseau form (24 automorphisms) on 2^24 gates
        let ps = perms(); let mut mism = 0u64;
        for g in (0u32..(1u32 << 24)).map(|i| i.wrapping_mul(2654435761)) {
            let d = universal(g);
            let r = !has_closed_subset(g) && !has_congruence(g) && !ps[1..].iter().any(|s| is_auto(g, s));
            if d != r { mism += 1; }
        }
        let j = format!(
            "{{\n  \"k\": 4,\n  \"total_gates\": {},\n  \"universal\": {},\n  \"fraction\": {},\n  \"fail_subset\": {},\n  \"fail_congruence_only\": {},\n  \"fail_involution_only\": {},\n  \"universal_with_bijective_diagonal\": {},\n  \"burnside48_sum_all\": {},\n  \"orbits48_all\": {},\n  \"burnside48_sum_univ\": {},\n  \"orbits48_univ\": {},\n  \"davies_vs_rousseau_mismatches_on_2e24_sample\": {},\n  \"wall_s\": {:.1},\n  \"fix\": [{}]\n}}\n",
            1u64 << 32, nu, nu as f64 / (1u64 << 32) as f64, n_sub, n_cong, n_inv, bij,
            fix_all, fix_all as f64 / 48.0, fix_u, fix_u as f64 / 48.0, mism, t0.elapsed().as_secs_f64(), detail.join(",")
        );
        atomic_write(&format!("{}.json", out_dir.trim_end_matches('/')), &j);
        print!("{}", j);
    }
}
