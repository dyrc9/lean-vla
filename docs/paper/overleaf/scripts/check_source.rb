#!/usr/bin/env ruby
# frozen_string_literal: true

require "pathname"

root = Pathname.new(__dir__).parent
manifest_path = root / "sync_manifest.txt"
abort "missing sync_manifest.txt" unless manifest_path.file?

manifest = manifest_path.readlines(chomp: true).reject { |line| line.empty? || line.start_with?("#") }
missing_manifest_files = manifest.reject { |relative| (root / relative).file? }
unless missing_manifest_files.empty?
  abort "missing manifest files: #{missing_manifest_files.join(', ')}"
end

main_path = root / "paper_ndss.tex"
main = main_path.read

missing_inputs = main.scan(/\\input\{([^}]+)\}/).flatten.reject do |relative|
  (root / "#{relative}.tex").file?
end
abort "missing LaTeX inputs: #{missing_inputs.join(', ')}" unless missing_inputs.empty?

tex = manifest
  .select { |relative| relative.end_with?(".tex") }
  .map { |relative| (root / relative).read }
  .join("\n")
bib = (root / "paper.bib").read

cited = tex.scan(/\\cite\{([^}]+)\}/)
  .flatten
  .flat_map { |keys| keys.split(",") }
  .map(&:strip)
  .uniq
defined = bib.scan(/^@\w+\{([^,]+),/).flatten.uniq

missing_citations = cited - defined
unused_citations = defined - cited
abort "undefined citations: #{missing_citations.join(', ')}" unless missing_citations.empty?
abort "unused bibliography entries: #{unused_citations.join(', ')}" unless unused_citations.empty?

duplicate_keys = bib.scan(/^@\w+\{([^,]+),/).flatten
  .group_by { |key| key }
  .select { |_key, values| values.length > 1 }
  .keys
abort "duplicate bibliography keys: #{duplicate_keys.join(', ')}" unless duplicate_keys.empty?

unless main.include?("\\bibliography{paper}")
  abort "paper_ndss.tex must use paper.bib"
end

puts "source tree: OK (#{manifest.length} synchronized files)"
puts "LaTeX inputs: OK"
puts "citations: OK (#{cited.length} cited, #{defined.length} defined)"
