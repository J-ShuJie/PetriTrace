import unittest,itertools
import numpy as np
from tools.mcount_cli import solve_assignment
class AssignmentTests(unittest.TestCase):
 def test_relaxation_matches_exhaustive_integer_assignments(self):
  rng=np.random.default_rng(42)
  for rows,cols in [(2,2),(3,3),(5,3),(4,4)]:
   for _ in range(6):
    distances=rng.uniform(0,60,(rows,cols));lam=30.
    expected=min(sum(distances[i,j] for i,j in enumerate(assign))+len(set(assign))*lam for assign in itertools.product(range(cols),repeat=rows))
    result=solve_assignment(distances,lam)
    self.assertAlmostEqual(result.fun,expected,places=6)
if __name__=='__main__':unittest.main()
