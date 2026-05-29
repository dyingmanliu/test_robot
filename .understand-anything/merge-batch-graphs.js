const fs = require('fs');
const path = require('path');

// Simple merge of all batch-N.json files into assembled-graph.json
function mergeBatchGraphs(intermediateDir, outputPath) {
  const allNodes = [];
  const allEdges = [];
  const nodeIds = new Set();
  const edgeKeys = new Set();

  const files = fs.readdirSync(intermediateDir)
    .filter(f => /^batch-\d+\.json$/.test(f))
    .sort((a, b) => {
      const na = parseInt(a.match(/\d+/)[0]);
      const nb = parseInt(b.match(/\d+/)[0]);
      return na - nb;
    });

  console.log(`Found ${files.length} batch files to merge`);

  for (const file of files) {
    const filePath = path.join(intermediateDir, file);
    const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    
    // Deduplicate nodes
    if (data.nodes) {
      for (const node of data.nodes) {
        if (!nodeIds.has(node.id)) {
          nodeIds.add(node.id);
          allNodes.push(node);
        }
      }
    }

    // Deduplicate edges
    if (data.edges) {
      for (const edge of data.edges) {
        const key = `${edge.source}|${edge.target}|${edge.type}`;
        if (!edgeKeys.has(key)) {
          edgeKeys.add(key);
          allEdges.push(edge);
        }
      }
    }

    console.log(`  ${file}: ${(data.nodes || []).length} nodes, ${(data.edges || []).length} edges`);
  }

  const result = { nodes: allNodes, edges: allEdges };
  fs.writeFileSync(outputPath, JSON.stringify(result, null, 2));
  console.log(`\nAssembled graph: ${allNodes.length} unique nodes, ${allEdges.length} unique edges`);
  console.log(`Written to: ${outputPath}`);
}

const intermediateDir = '/Users/qiunian/Documents/test/test-robots/.understand-anything/intermediate';
const outputPath = '/Users/qiunian/Documents/test/test-robots/.understand-anything/intermediate/assembled-graph.json';
mergeBatchGraphs(intermediateDir, outputPath);
