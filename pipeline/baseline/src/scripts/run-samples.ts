import path from 'node:path';

import { promises as fs } from 'node:fs';

import { runBaselineModule } from '../pipeline';

interface SampleJob {
  inputPath: string;
  outputPath: string;
}

async function runSampleJobs(jobs: SampleJob[]): Promise<void> {
  for (const job of jobs) {
    const summary = await runBaselineModule(job.inputPath, job.outputPath);
    console.log(`Generated ${summary.rowCount} rows for ${summary.schemaName} at ${summary.outputPath}`);
  }
}

async function main(): Promise<void> {
  const rootDir = path.resolve(process.cwd());
  const sampleDir = path.join(rootDir, 'test-data');
  const outputDir = path.join(rootDir, 'sample-output');

  await fs.mkdir(outputDir, { recursive: true });

  await runSampleJobs([
    {
      inputPath: path.join(sampleDir, 'toy-library.json'),
      outputPath: path.join(outputDir, 'toy-library-baseline_results.csv')
    },
    {
      inputPath: path.join(sampleDir, 'toy-retail.json'),
      outputPath: path.join(outputDir, 'toy-retail-baseline_results.csv')
    }
  ]);

  console.log('Sample run complete. Compare the generated CSV files in sample-output/.');
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Sample run failed: ${message}`);
  process.exit(1);
});