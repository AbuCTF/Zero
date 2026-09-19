<svelte:head>
	<title>ZeroPool</title>
	<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
</svelte:head>

<div class="relative min-h-screen overflow-hidden bg-background font-sans">
	<nav class="fixed top-0 left-0 right-0 z-50 border-b border-border/40 bg-background/80 backdrop-blur-xl">
		<div class="mx-auto max-w-6xl px-4 sm:px-6">
			<div class="flex h-16 items-center justify-between">
				<a href="/" class="group flex items-center">
					<img src="/logo.png" alt="ZeroPool" class="h-9 w-auto transition-transform group-hover:scale-105" />
				</a>
				<div class="flex items-center gap-1 sm:gap-3">
					<a href="/verify" class="px-2 py-2 text-xs font-medium text-foreground-muted transition-colors hover:text-foreground sm:px-4 sm:text-sm">
						Verify
					</a>
					<a href="/portal/login" class="ml-1 rounded-full bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition-all hover:bg-primary/90 sm:ml-2 sm:px-5 sm:text-sm">
						Portal
					</a>
				</div>
			</div>
		</div>
	</nav>

	<div class="pointer-events-none absolute inset-0 z-0" aria-hidden="true">
		<div
			class="absolute inset-0"
			style="
				background-image:
					linear-gradient(hsl(var(--border) / 0.55) 1px, transparent 1px),
					linear-gradient(90deg, hsl(var(--border) / 0.55) 1px, transparent 1px);
				background-size: 58px 58px;
				-webkit-mask-image: radial-gradient(ellipse 78% 68% at 50% 44%, #000 28%, transparent 78%);
				mask-image: radial-gradient(ellipse 78% 68% at 50% 44%, #000 28%, transparent 78%);
			"
		></div>
		<div
			class="absolute left-1/2 top-1/2 h-[760px] w-[1120px] max-w-[150vw] -translate-x-1/2 -translate-y-1/2"
			style="background: radial-gradient(closest-side, hsl(var(--primary) / 0.13), transparent 72%);"
		></div>
	</div>

	<section class="relative z-10 flex min-h-screen items-center justify-center px-6 py-24">
		<div class="mx-auto max-w-3xl text-center">
			<div class="mb-7 inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-3.5 py-1.5 text-xs font-medium text-foreground-muted backdrop-blur-sm">
				<span class="h-1.5 w-1.5 rounded-full bg-primary"></span>
				Free-tier SMTP, pooled
			</div>

			<h1 class="text-5xl font-bold leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl">
				<span class="text-foreground">Pool Your</span><br />
				<span class="bg-gradient-to-br from-primary via-primary to-primary/60 bg-clip-text text-transparent">Free Emails</span>
			</h1>

			<p class="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-foreground-muted">
				Aggregate free-tier SMTP into one reliable sender. No monthly bill for basic email.
			</p>

			<div class="mt-9 flex flex-col items-center justify-center gap-4 sm:flex-row">
				<a href="/portal/login" class="group flex items-center gap-2 rounded-full bg-primary px-8 py-3.5 text-base font-semibold text-primary-foreground shadow-lg shadow-primary/25 transition-all hover:-translate-y-0.5 hover:bg-primary/90 hover:shadow-xl hover:shadow-primary/30">
					Open Portal
					<svg class="h-4 w-4 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
					</svg>
				</a>
				<a href="/verify" class="rounded-full border border-primary/40 px-8 py-3.5 text-base font-semibold text-foreground transition-all hover:border-primary hover:bg-primary hover:text-primary-foreground">
					Verify Certificate
				</a>
			</div>

			<div class="mt-16 flex flex-col items-center gap-3.5">
				<span class="text-[11px] font-semibold uppercase tracking-[0.16em] text-foreground-muted/60">
					Pools your free tiers from
				</span>
				<div class="flex flex-wrap items-center justify-center gap-x-6 gap-y-2.5 text-sm font-medium text-foreground-muted/90">
					<span>Mailgun</span>
					<span class="h-1 w-1 rounded-full bg-border"></span>
					<span>Brevo</span>
					<span class="h-1 w-1 rounded-full bg-border"></span>
					<span>SendGrid</span>
					<span class="h-1 w-1 rounded-full bg-border"></span>
					<span>Google App Passwords</span>
				</div>
			</div>
		</div>
	</section>
</div>
