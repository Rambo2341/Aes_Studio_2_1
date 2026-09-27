from __future__ import annotations
"""Verified self-training drills.

Aes answers freshly generated problems whose correct answer the computer can check
(maths by exact computation, code by hidden tests). Only verified-correct answers become
training examples; wrong answers become correction examples with the true answer.
This gives a clean, honest training signal every day without copying anyone's model.
"""
import json, os, random, re, subprocess, sys, tempfile
from fractions import Fraction


# ---- maths generators: (question, exact_answer_string) ----------------------
def _arith(r):
    a, b, c = r.randint(12, 999), r.randint(2, 99), r.randint(2, 40)
    return f'Compute ({a} * {b}) - {c}^2 + {a} // {c}. Use integer division for //.', str(a * b - c * c + a // c)

def _fraction(r):
    a, b, c, d = (r.randint(1, 15) for _ in range(4))
    return f'Compute {a}/{b + 1} + {c}/{d + 1} as a fully reduced fraction p/q.', str(Fraction(a, b + 1) + Fraction(c, d + 1))

def _linear(r):
    x = r.randint(-20, 20); a = r.choice([i for i in range(-9, 10) if i]); b = r.randint(-50, 50)
    return f'Solve for x: {a}x + ({b}) = {a * x + b}.', str(x)

def _system(r):
    x, y = r.randint(-9, 9), r.randint(-9, 9)
    while True:
        a, b, c, d = (r.randint(-6, 6) for _ in range(4))
        if a * d - b * c: break
    return (f'Solve the system: {a}x + {b}y = {a*x + b*y} and {c}x + {d}y = {c*x + d*y}. Answer as x,y.', f'{x},{y}')

def _derivative(r):
    n, k = r.randint(2, 7), r.randint(2, 9); x0 = r.randint(1, 4)
    return f'Let f(x) = {k}x^{n}. What is f\'({x0})? Give an integer.', str(k * n * x0 ** (n - 1))

def _integral(r):
    n = r.randint(1, 5); up = r.randint(1, 4)
    return f'Compute the definite integral of {n + 1}x^{n} from 0 to {up}. Give an integer.', str(up ** (n + 1))

def _prob(r):
    n = r.randint(2, 4)
    return f'You roll {n} fair six-sided dice. What is the probability that all show the same number? Answer as a reduced fraction.', str(Fraction(6, 6 ** n))

def _combin(r):
    n = r.randint(6, 14); k = r.randint(2, 5)
    from math import comb
    return f'How many ways can you choose {k} items from {n} distinct items? Give an integer.', str(comb(n, k))

def _modular(r):
    a, e, m = r.randint(2, 30), r.randint(20, 200), r.choice([7, 11, 13, 17, 19, 23, 97])
    return f'Compute {a}^{e} mod {m}.', str(pow(a, e, m))

def _physics(r):
    v, t = r.randint(5, 40), r.randint(1, 6)
    return (f'A car starts at {v} m/s and accelerates at 2 m/s^2 for {t} s. How far does it travel in metres? Give an integer.', str(v * t + t * t))

def _chem(r):
    comps = {'H2O': Fraction(1801528, 100000), 'CO2': Fraction(4400950, 100000), 'NaCl': Fraction(5844, 100), 'CH4': Fraction(1604246, 100000)}
    f = r.choice(list(comps)); g = r.randint(2, 9) * 10
    return (f'How many moles are in {g} g of {f}? Use molar mass {float(comps[f]):.2f} g/mol. Round to 2 decimals.', f'{float(g / round(comps[f], 2)):.2f}')

MATH = [_arith, _fraction, _linear, _system, _derivative, _integral, _prob, _combin, _modular, _physics, _chem]


# ---- code katas: (task, function name, tests) --------------------------------
KATAS = [
    ('Write a Python function is_prime(n) returning True if n is prime.', 'is_prime', [((2,), True), ((1,), False), ((97,), True), ((91,), False)]),
    ('Write a Python function fib(n) returning the n-th Fibonacci number with fib(0)=0, fib(1)=1.', 'fib', [((0,), 0), ((1,), 1), ((10,), 55), ((30,), 832040)]),
    ('Write a Python function rev_words(s) that reverses the order of words separated by single spaces.', 'rev_words', [(('a b c',), 'c b a'), (('hello',), 'hello')]),
    ('Write a Python function gcd(a, b) using the Euclidean algorithm (non-negative ints).', 'gcd', [((12, 18), 6), ((17, 5), 1), ((0, 9), 9)]),
    ('Write a Python function is_palindrome(s) ignoring case and non-alphanumeric characters.', 'is_palindrome', [(('A man, a plan, a canal: Panama',), True), (('abc',), False)]),
    ('Write a Python function flatten(lst) that flattens arbitrarily nested lists.', 'flatten', [(([1, [2, [3, [4]]], 5],), [1, 2, 3, 4, 5]), (([],), [])]),
    ('Write a Python function two_sum(nums, target) returning the sorted pair of indices whose values sum to target.', 'two_sum', [(([2, 7, 11, 15], 9), [0, 1]), (([3, 2, 4], 6), [1, 2])]),
    ('Write a Python function binary_search(arr, x) returning the index of x in sorted arr or -1.', 'binary_search', [(([1, 3, 5, 7], 5), 2), (([1, 3, 5, 7], 4), -1)]),
    ('Write a Python function roman(n) converting 1..3999 to Roman numerals.', 'roman', [((4,), 'IV'), ((1994,), 'MCMXCIV'), ((3999,), 'MMMCMXCIX')]),
    ('Write a Python function lis(nums) returning the length of the longest strictly increasing subsequence.', 'lis', [(([10, 9, 2, 5, 3, 7, 101, 18],), 4), (([],), 0)]),
    ('Write a Python function balanced(s) returning True if the brackets ()[]{} in s are balanced.', 'balanced', [(('([]{})',), True), (('([)]',), False), (('',), True)]),
    ('Write a Python function word_freq(s) returning a dict of lowercase word counts (split on whitespace).', 'word_freq', [(('a A b',), {'a': 2, 'b': 1})]),
]


def normalize(ans: str) -> str:
    ans = (ans or '').strip()
    m = re.search(r'(?:final answer|answer)\s*[:=]\s*(.+)', ans, re.I)
    if m: ans = m.group(1)
    ans = ans.strip().strip('.').replace(' ', '').replace('$', '').replace('\\', '')
    ans = re.sub(r'(?i)(?<![a-z])[xy]=', '', ans)
    return ans.strip('()').lower()


def math_matches(answer: str, truth: str) -> bool:
    got = normalize(answer.splitlines()[-1] if answer.strip() else '')
    if got == truth.lower(): return True
    try:
        return abs(float(Fraction(got)) - float(Fraction(truth))) < 1e-9
    except Exception:
        return False


def extract_code(answer: str) -> str:
    m = re.findall(r'```(?:python|py)?\s*\n(.*?)```', answer or '', re.S)
    return m[0] if m else (answer or '')


def run_kata(code: str, fn: str, tests, timeout=20):
    harness = code + '\n\nimport json,sys\n_res=[]\nfor args,exp in json.loads(sys.argv[1]):\n    try: _res.append(' + fn + '(*args)==exp)\n    except Exception: _res.append(False)\nprint(json.dumps(_res))\n'
    fd, path = tempfile.mkstemp(suffix='.py'); os.close(fd)
    try:
        with open(path, 'w', encoding='utf-8') as f: f.write(harness)
        cp = subprocess.run([sys.executable, path, json.dumps([[list(a), e] for a, e in tests])], capture_output=True, text=True, timeout=timeout)
        res = json.loads(cp.stdout.strip().splitlines()[-1]) if cp.stdout.strip() else []
        return bool(res) and all(res)
    except Exception:
        return False
    finally:
        try: os.remove(path)
        except Exception: pass


def run_drills(complete, n_math=20, n_code=6, seed=None):
    """complete(messages)->str. Returns stats + training examples (only verified content)."""
    r = random.Random(seed)
    examples = []; math_ok = 0; code_ok = 0
    sys_msg = {'role': 'system', 'content': 'You are Aes. Solve carefully. End with a final line "Answer: <answer>".'}
    for _ in range(n_math):
        q, truth = r.choice(MATH)(r)
        ans = complete([sys_msg, {'role': 'user', 'content': q}]).strip()
        if math_matches(ans, truth):
            math_ok += 1; examples.append(([{'role': 'user', 'content': q}, {'role': 'assistant', 'content': ans}], 'drill:math', 2))
        else:
            examples.append(([{'role': 'user', 'content': q}, {'role': 'assistant', 'content': f'Answer: {truth}'}], 'drill:math-correction', 1))
    for task, fn, tests in r.sample(KATAS, min(n_code, len(KATAS))):
        prompt = task + ' Return only the code in one ```python block.'
        ans = complete([{'role': 'system', 'content': 'You are Aes, an expert programmer.'}, {'role': 'user', 'content': prompt}]).strip()
        if run_kata(extract_code(ans), fn, tests):
            code_ok += 1; examples.append(([{'role': 'user', 'content': prompt}, {'role': 'assistant', 'content': ans}], 'drill:code', 2))
    return {'math_ok': math_ok, 'math_total': n_math, 'code_ok': code_ok, 'code_total': min(n_code, len(KATAS)), 'examples': examples}
