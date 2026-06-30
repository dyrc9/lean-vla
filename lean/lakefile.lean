import Lake
open Lake DSL

package proofalign where
  srcDir := "."

lean_lib ProofAlign where
  roots := #[`ProofAlign]
