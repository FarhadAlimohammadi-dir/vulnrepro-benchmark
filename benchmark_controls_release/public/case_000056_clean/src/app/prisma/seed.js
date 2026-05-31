const { PrismaClient } = require('@prisma/client');
const crypto = require('crypto');
const prisma = new PrismaClient();

async function main() {
  const userCount = await prisma.user.count();
  if (userCount > 0) {
    console.log('Database already seeded, skipping...');
    return;
  }

  console.log('Seeding categories...');
  const catTech = await prisma.category.create({
    data: { name: 'Technology', slug: 'technology', description: 'Tech news and tutorials' }
  });
  const catBusiness = await prisma.category.create({
    data: { name: 'Business', slug: 'business', description: 'Business and finance insights' }
  });
  const catDesign = await prisma.category.create({
    data: { name: 'Design', slug: 'design', description: 'UI/UX and visual design' }
  });
  const catScience = await prisma.category.create({
    data: { name: 'Science', slug: 'science', description: 'Scientific discoveries and research' }
  });

  console.log('Seeding users...');
  const alice = await prisma.user.create({
    data: {
      email: 'alice@example.com',
      name: 'Alice Chen',
      password: 'alice_secret_pwd_123',
      isAdmin: true,
      bio: 'Chief Editor and Platform Administrator. 10+ years in digital publishing.',
      resetToken: crypto.randomBytes(8).toString('hex')
    }
  });

  const bob = await prisma.user.create({
    data: {
      email: 'bob@example.com',
      name: 'Bob Martinez',
      password: 'bob_super_secret_456',
      isAdmin: false,
      bio: 'Senior Technology Writer. Covers cloud infrastructure and DevOps.',
      resetToken: crypto.randomBytes(8).toString('hex')
    }
  });

  const charlie = await prisma.user.create({
    data: {
      email: 'charlie@example.com',
      name: 'Charlie Kim',
      password: 'charlie_pass_789_secure',
      isAdmin: false,
      bio: 'Business & Finance Correspondent with background in investment banking.',
      resetToken: crypto.randomBytes(8).toString('hex')
    }
  });

  const diana = await prisma.user.create({
    data: {
      email: 'diana@example.com',
      name: 'Diana Okafor',
      password: 'diana_pwd_editorial_321',
      isAdmin: false,
      bio: 'Design Lead and Visual Storyteller.',
      resetToken: crypto.randomBytes(8).toString('hex')
    }
  });

  const evan = await prisma.user.create({
    data: {
      email: 'evan@example.com',
      name: 'Evan Patel',
      password: 'evan_secure_pass_654',
      isAdmin: false,
      bio: 'Science Journalist covering biotech and climate research.',
      resetToken: crypto.randomBytes(8).toString('hex')
    }
  });

  console.log('Seeding articles...');
  const articles = [
    {
      title: 'Getting Started with Prisma ORM',
      slug: 'getting-started-with-prisma-orm',
      body: 'Prisma is a next-generation ORM that makes database access easy with an auto-generated and type-safe query builder for Node.js & TypeScript. In this comprehensive guide, we explore the fundamentals of setting up Prisma in a new project and migrating your first schema.',
      summary: 'A complete introduction to Prisma ORM for modern Node.js applications.',
      published: true,
      featured: true,
      viewCount: 4821,
      tags: ['prisma', 'nodejs', 'database', 'orm'],
      createdById: alice.id,
      categoryId: catTech.id
    },
    {
      title: 'Scaling PostgreSQL for High-Traffic Applications',
      slug: 'scaling-postgresql-high-traffic',
      body: 'PostgreSQL remains one of the most capable relational databases available today. This article covers connection pooling with PgBouncer, read replicas, partitioning strategies, and indexing best practices for applications handling millions of requests per day.',
      summary: 'Performance optimization techniques for PostgreSQL at scale.',
      published: true,
      featured: false,
      viewCount: 3102,
      tags: ['postgresql', 'performance', 'database', 'devops'],
      createdById: bob.id,
      categoryId: catTech.id
    },
    {
      title: 'The State of Remote Work in 2024',
      slug: 'state-of-remote-work-2024',
      body: 'Four years after the widespread adoption of remote work, organizations are grappling with hybrid models, productivity measurement, and culture building. Our survey of 2,400 knowledge workers reveals surprising insights about preferences and performance.',
      summary: 'Survey results and analysis on remote work trends across industries.',
      published: true,
      featured: true,
      viewCount: 7890,
      tags: ['remote-work', 'productivity', 'culture'],
      createdById: charlie.id,
      categoryId: catBusiness.id
    },
    {
      title: 'Design Systems at Enterprise Scale',
      slug: 'design-systems-enterprise-scale',
      body: 'Building and maintaining a design system for a large organization requires more than just a component library. This article examines governance models, versioning strategies, contribution workflows, and the organizational dynamics that determine success or failure.',
      summary: 'Practical guidance for scaling design systems across large organizations.',
      published: true,
      featured: false,
      viewCount: 2341,
      tags: ['design-systems', 'ux', 'enterprise', 'components'],
      createdById: diana.id,
      categoryId: catDesign.id
    },
    {
      title: 'CRISPR Gene Editing: 2024 Progress Report',
      slug: 'crispr-gene-editing-2024-progress',
      body: 'The past year has seen remarkable advances in CRISPR-based therapeutics, with multiple clinical trials reporting positive outcomes for sickle cell disease, beta-thalassemia, and several forms of hereditary blindness. We examine the scientific breakthroughs and remaining challenges.',
      summary: 'A comprehensive review of CRISPR clinical progress and future directions.',
      published: true,
      featured: false,
      viewCount: 1987,
      tags: ['crispr', 'genetics', 'medicine', 'biotech'],
      createdById: evan.id,
      categoryId: catScience.id
    },
    {
      title: 'Building Resilient Microservices with Node.js',
      slug: 'resilient-microservices-nodejs',
      body: 'Circuit breakers, bulkheads, and retry logic are essential patterns for building fault-tolerant distributed systems. This deep-dive explores implementing these patterns in Node.js using proven libraries and discusses tradeoffs between complexity and reliability.',
      summary: 'Fault tolerance patterns for Node.js microservice architectures.',
      published: true,
      featured: false,
      viewCount: 2654,
      tags: ['nodejs', 'microservices', 'architecture', 'resilience'],
      createdById: bob.id,
      categoryId: catTech.id
    },
    {
      title: 'Venture Capital Funding Trends Q3 2024',
      slug: 'vc-funding-trends-q3-2024',
      body: 'Deal volume declined 18% year-over-year in Q3, but valuations for AI-adjacent companies continue to defy gravity. Our analysis of 1,200 funding rounds reveals which sectors are attracting capital and which are struggling to close rounds.',
      summary: 'Analysis of venture capital activity and emerging investment themes.',
      published: true,
      featured: false,
      viewCount: 3421,
      tags: ['venture-capital', 'startups', 'investment', 'ai'],
      createdById: charlie.id,
      categoryId: catBusiness.id
    },
    {
      title: 'Typography in the Age of Variable Fonts',
      slug: 'typography-variable-fonts',
      body: 'Variable fonts represent a paradigm shift in web typography, offering unprecedented control over weight, width, optical size, and custom axes. We explore practical implementation strategies and highlight exceptional examples from recent digital publications.',
      summary: 'Exploring the creative and technical potential of variable fonts.',
      published: true,
      featured: false,
      viewCount: 1543,
      tags: ['typography', 'variable-fonts', 'web-design', 'css'],
      createdById: diana.id,
      categoryId: catDesign.id
    },
    {
      title: 'Ocean Carbon Capture: Promise and Pitfalls',
      slug: 'ocean-carbon-capture-analysis',
      body: 'Marine carbon dioxide removal technologies — from seaweed farming to ocean alkalinity enhancement — have attracted billions in climate tech investment. But scientific uncertainty, ecosystem risks, and measurement challenges complicate the picture significantly.',
      summary: 'Critical analysis of ocean-based carbon removal approaches.',
      published: true,
      featured: false,
      viewCount: 1876,
      tags: ['climate', 'carbon-capture', 'ocean', 'environment'],
      createdById: evan.id,
      categoryId: catScience.id
    },
    {
      title: 'Draft: Platform Monetization Strategy 2025',
      slug: 'platform-monetization-strategy-2025',
      body: 'Internal draft for Q1 planning. Subscription tiers, sponsored content policies, and API access pricing under review.',
      summary: 'Internal strategy document — not for publication.',
      published: false,
      featured: false,
      viewCount: 0,
      tags: ['internal', 'strategy'],
      createdById: alice.id,
      categoryId: catBusiness.id
    },
    {
      title: 'Kubernetes Cost Optimization Strategies',
      slug: 'kubernetes-cost-optimization',
      body: 'Cloud infrastructure costs for Kubernetes workloads can spiral quickly without proper governance. This guide covers right-sizing, spot instances, cluster autoscaling, and FinOps practices that leading engineering organizations use to reduce spend by 40-60%.',
      summary: 'Reduce Kubernetes infrastructure costs without sacrificing reliability.',
      published: true,
      featured: false,
      viewCount: 3891,
      tags: ['kubernetes', 'cloud', 'cost-optimization', 'devops'],
      createdById: bob.id,
      categoryId: catTech.id
    },
    {
      title: 'The Psychology of Color in Brand Identity',
      slug: 'psychology-color-brand-identity',
      body: 'Color choices in brand identity systems carry significant psychological weight. Drawing on research across cultural contexts and consumer behavior studies, this piece examines how leading brands leverage color theory and what aspiring designers can learn from their choices.',
      summary: 'How color psychology shapes brand perception and consumer behavior.',
      published: true,
      featured: false,
      viewCount: 2109,
      tags: ['branding', 'color-theory', 'psychology', 'design'],
      createdById: diana.id,
      categoryId: catDesign.id
    }
  ];

  for (const article of articles) {
    await prisma.article.create({ data: article });
  }

  console.log('Seeding comments...');
  const publishedArticles = await prisma.article.findMany({ where: { published: true }, take: 5 });
  for (const article of publishedArticles) {
    await prisma.comment.create({
      data: {
        body: 'Great article, very informative!',
        approved: true,
        authorId: bob.id,
        articleId: article.id
      }
    });
    await prisma.comment.create({
      data: {
        body: 'This really helped me understand the topic better.',
        approved: true,
        authorId: charlie.id,
        articleId: article.id
      }
    });
  }

  console.log('Seeding audit logs...');
  await prisma.auditLog.createMany({
    data: [
      { action: 'USER_LOGIN', entityType: 'User', entityId: alice.id, details: 'Login from 192.168.1.10', userId: alice.id },
      { action: 'ARTICLE_PUBLISHED', entityType: 'Article', entityId: 1, details: 'Article published by admin', userId: alice.id },
      { action: 'USER_LOGIN', entityType: 'User', entityId: bob.id, details: 'Login from 10.0.0.42', userId: bob.id },
      { action: 'ARTICLE_CREATED', entityType: 'Article', entityId: 2, details: 'New article created', userId: bob.id },
      { action: 'COMMENT_APPROVED', entityType: 'Comment', entityId: 1, details: 'Comment approved by moderator', userId: alice.id },
      { action: 'USER_PROFILE_UPDATED', entityType: 'User', entityId: charlie.id, details: 'Bio updated', userId: charlie.id },
      { action: 'ARTICLE_FEATURED', entityType: 'Article', entityId: 3, details: 'Article marked as featured', userId: alice.id },
      { action: 'CATEGORY_CREATED', entityType: 'Category', entityId: catTech.id, details: 'Technology category created', userId: alice.id }
    ]
  });

  console.log('Seed completed successfully.');
}

main()
  .catch(e => {
    console.error('Seed error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });