/**
 * Phase 6 API Test Suite
 * Tests all Phase 6 endpoints to confirm they're working
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://aiclone-production-32dc.up.railway.app';
const TEST_USER_ID = 'dev-user-test';

interface TestResult {
  endpoint: string;
  method: string;
  status: 'pass' | 'fail' | 'skip';
  message: string;
  response?: any;
  error?: string;
}

const results: TestResult[] = [];

async function testEndpoint(
  name: string,
  method: string,
  endpoint: string,
  body?: any,
  expectedStatus: number = 200
): Promise<TestResult> {
  try {
    const url = `${API_URL}${endpoint}`;
    const options: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const startTime = Date.now();
    const response = await fetch(url, options);
    const duration = Date.now() - startTime;
    
    let responseData;
    try {
      responseData = await response.json();
    } catch {
      responseData = { text: await response.text() };
    }

    const passed = response.status === expectedStatus || response.status < 400;
    
    return {
      endpoint: name,
      method,
      status: passed ? 'pass' : 'fail',
      message: passed 
        ? `✅ ${response.status} (${duration}ms)`
        : `❌ ${response.status} - ${responseData.detail || responseData.message || 'Unknown error'}`,
      response: responseData,
    };
  } catch (error: any) {
    return {
      endpoint: name,
      method,
      status: 'fail',
      message: `❌ Error: ${error.message}`,
      error: error.message,
    };
  }
}

async function runTests() {
  console.log('🧪 Phase 6 API Test Suite\n');
  console.log(`Testing against: ${API_URL}\n`);
  console.log('='.repeat(60));

  // 6.1: Predictive Analytics
  console.log('\n📊 Testing Predictive Analytics...');
  results.push(await testEndpoint(
    'Get Optimal Posting Time',
    'GET',
    `/api/predictive/optimal-posting-time?user_id=${TEST_USER_ID}`
  ));

  results.push(await testEndpoint(
    'Predict Prospect Conversion',
    'POST',
    `/api/predictive/prospect/test-prospect-id/predict-conversion?user_id=${TEST_USER_ID}`,
    null,
    404 // Expected 404 since prospect doesn't exist
  ));

  // 6.1: Recommendations
  console.log('\n🎯 Testing Recommendation Engine...');
  results.push(await testEndpoint(
    'Get Prospect Recommendations',
    'GET',
    `/api/recommendations/prospects?user_id=${TEST_USER_ID}&limit=5`
  ));

  results.push(await testEndpoint(
    'Get Content Topic Recommendations',
    'GET',
    `/api/recommendations/content-topics?user_id=${TEST_USER_ID}&limit=5`
  ));

  results.push(await testEndpoint(
    'Get Outreach Angle Recommendations',
    'GET',
    `/api/recommendations/outreach-angles?user_id=${TEST_USER_ID}`
  ));

  results.push(await testEndpoint(
    'Get Hashtag Recommendations',
    'GET',
    `/api/recommendations/hashtags?user_id=${TEST_USER_ID}&limit=5`
  ));

  // 6.1: NLP
  console.log('\n🧠 Testing NLP Services...');
  results.push(await testEndpoint(
    'Detect Intent',
    'POST',
    '/api/nlp/detect-intent',
    { text: 'I am interested in learning more about your product' }
  ));

  results.push(await testEndpoint(
    'Extract Entities',
    'POST',
    '/api/nlp/extract-entities',
    { text: 'John Smith works at Acme Corp in the technology industry' }
  ));

  results.push(await testEndpoint(
    'Summarize Text',
    'POST',
    '/api/nlp/summarize?max_sentences=3',
    { text: 'This is a long text that needs to be summarized. It contains multiple sentences and ideas. The summarization should extract the key points and present them concisely.' }
  ));

  results.push(await testEndpoint(
    'Analyze Sentiment',
    'POST',
    '/api/nlp/analyze-sentiment',
    { text: 'This is a great product! I love it.' }
  ));

  // 6.1: Content Optimization
  console.log('\n✨ Testing Content Optimization...');
  results.push(await testEndpoint(
    'Score Content Quality',
    'POST',
    '/api/content-optimization/score',
    {
      content: 'This is a sample LinkedIn post with some hashtags #AI #EdTech #Innovation',
      metadata: {
        hashtags: ['AI', 'EdTech', 'Innovation']
      }
    }
  ));

  results.push(await testEndpoint(
    'Create A/B Test Variants',
    'POST',
    '/api/content-optimization/ab-test/variants?num_variants=3',
    {
      base_content: 'This is a test post for A/B testing purposes.'
    }
  ));

  // 6.4: Business Intelligence
  console.log('\n📈 Testing Business Intelligence...');
  results.push(await testEndpoint(
    'Get Executive Dashboard',
    'GET',
    `/api/bi/executive-dashboard?user_id=${TEST_USER_ID}&days=30`
  ));

  // 6.4: Advanced Reporting
  console.log('\n📋 Testing Advanced Reporting...');
  const endDate = new Date().toISOString();
  const startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
  const startDate2 = new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString();
  const endDate2 = new Date(Date.now() - 31 * 24 * 60 * 60 * 1000).toISOString();

  results.push(await testEndpoint(
    'Generate Comparative Report',
    'POST',
    `/api/reporting/comparative?user_id=${TEST_USER_ID}&metric=prospects&period1_start=${startDate2}&period1_end=${endDate2}&period2_start=${startDate}&period2_end=${endDate}`
  ));

  // 6.4: Predictive Insights
  console.log('\n🔮 Testing Predictive Insights...');
  results.push(await testEndpoint(
    'Forecast Revenue',
    'GET',
    `/api/predictive-insights/forecast/revenue?user_id=${TEST_USER_ID}&days_ahead=30`
  ));

  results.push(await testEndpoint(
    'Forecast Pipeline',
    'GET',
    `/api/predictive-insights/forecast/pipeline?user_id=${TEST_USER_ID}&days_ahead=30`
  ));

  results.push(await testEndpoint(
    'Detect Anomalies',
    'GET',
    `/api/predictive-insights/anomalies?user_id=${TEST_USER_ID}&metric_type=engagement&days=30`
  ));

  // 6.5: Multi-Format Content Generation
  console.log('\n📝 Testing Multi-Format Content Generation...');
  results.push(await testEndpoint(
    'Generate Blog Post',
    'POST',
    '/api/content/generate/blog',
    {
      topic: 'AI in Education',
      length: 'short',
      tone: 'professional'
    }
  ));

  results.push(await testEndpoint(
    'Generate Email',
    'POST',
    '/api/content/generate/email',
    {
      subject: 'Introduction to Our Product',
      recipient_type: 'prospect',
      purpose: 'introduction',
      tone: 'professional'
    }
  ));

  results.push(await testEndpoint(
    'Generate Video Script',
    'POST',
    '/api/content/generate/video-script',
    {
      topic: 'How AI is Transforming Education',
      duration: 'short',
      style: 'educational'
    }
  ));

  results.push(await testEndpoint(
    'Generate White Paper',
    'POST',
    '/api/content/generate/white-paper',
    {
      topic: 'The Future of AI in Education',
      sections: []
    }
  ));

  // 6.5: Content Library
  console.log('\n📚 Testing Content Library...');
  results.push(await testEndpoint(
    'List Content Library',
    'GET',
    `/api/content-library?user_id=${TEST_USER_ID}&limit=10`
  ));

  // 6.5: Cross-Platform Analytics
  console.log('\n🌐 Testing Cross-Platform Analytics...');
  results.push(await testEndpoint(
    'Get Unified Performance',
    'GET',
    `/api/analytics/cross-platform/unified?user_id=${TEST_USER_ID}&days=30`
  ));

  // Print Results Summary
  console.log('\n' + '='.repeat(60));
  console.log('\n📊 Test Results Summary\n');

  const passed = results.filter(r => r.status === 'pass').length;
  const failed = results.filter(r => r.status === 'fail').length;
  const skipped = results.filter(r => r.status === 'skip').length;

  results.forEach(result => {
    console.log(`${result.message} - ${result.endpoint}`);
  });

  console.log('\n' + '='.repeat(60));
  console.log(`\n✅ Passed: ${passed}`);
  console.log(`❌ Failed: ${failed}`);
  console.log(`⏭️  Skipped: ${skipped}`);
  console.log(`📊 Total: ${results.length}`);
  
  const successRate = ((passed / results.length) * 100).toFixed(1);
  console.log(`\n🎯 Success Rate: ${successRate}%\n`);

  if (failed > 0) {
    console.log('\n❌ Failed Tests:');
    results
      .filter(r => r.status === 'fail')
      .forEach(r => {
        console.log(`\n  ${r.endpoint} (${r.method})`);
        console.log(`    Error: ${r.error || r.message}`);
        if (r.response) {
          console.log(`    Response: ${JSON.stringify(r.response, null, 2)}`);
        }
      });
  }

  return { passed, failed, skipped, total: results.length };
}

// Run tests
if (require.main === module) {
  runTests()
    .then(({ passed, failed }) => {
      process.exit(failed > 0 ? 1 : 0);
    })
    .catch(error => {
      console.error('Fatal error running tests:', error);
      process.exit(1);
    });
}

export { runTests, testEndpoint };

