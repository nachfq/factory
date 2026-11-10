/** Test-only UI fixture. Explicitly load alongside extension.mjs; never installed globally. */
export default function dialogFixture(pi) {
  pi.registerCommand('messaging-test-dialog', {
    description: 'Open a harmless 30-second confirmation to test message deferral; no action is authorized',
    handler: async (_args, ctx) => {
      pi.appendEntry('messaging-dialog-test', { phase: 'opened' });
      const confirmed = await ctx.ui.confirm(
        'Messaging test — no action will be taken',
        'This is only a message-deferral test. Neither answer authorizes any operation. Leave it open; it cancels automatically after 30 seconds.',
        { timeout: 30000 },
      );
      pi.appendEntry('messaging-dialog-test', { phase: 'closed', confirmed });
      ctx.ui.notify(`Test dialog closed (${confirmed ? 'yes' : 'no/cancel/timeout'}). No action taken.`, 'info');
    },
  });
}
