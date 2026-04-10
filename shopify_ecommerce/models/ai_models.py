from odoo import models, fields

class AIRecommendation(models.Model):
    _name        = 'shopify.ai.recommendation'
    _description = 'AI product recommendation'
    _order       = 'generated_at desc'

    customer_id   = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade')
    product_id    = fields.Many2one('product.template', string='Recommended product', required=True)
    rec_type      = fields.Selection([
        ('collaborative', 'Collaborative filtering'),
        ('content',       'Content-based'),
        ('hybrid',        'Hybrid'),
    ], string='Recommendation type')
    score         = fields.Float(string='Confidence score', digits=(5, 4))
    generated_at  = fields.Datetime(string='Generated', default=fields.Datetime.now)
    model_version = fields.Char(string='Model version')
    accepted      = fields.Boolean(string='Customer accepted', default=False)


class LeadScore(models.Model):
    _name        = 'shopify.lead.score'
    _description = 'AI lead conversion score'

    partner_id    = fields.Many2one('res.partner', string='Customer / lead', required=True, ondelete='cascade')
    score         = fields.Float(string='Conversion probability', digits=(5, 4))
    scored_at     = fields.Datetime(string='Scored at', default=fields.Datetime.now)
    features_json = fields.Text(string='Feature vector (JSON)')
    model_version = fields.Char(string='Model version')
    score_band    = fields.Selection([
        ('hot',  'Hot  (>0.7)'),
        ('warm', 'Warm (0.4–0.7)'),
        ('cold', 'Cold (<0.4)'),
    ], string='Score band', compute='_compute_band', store=True)

    def _compute_band(self):
        for rec in self:
            if rec.score >= 0.7:
                rec.score_band = 'hot'
            elif rec.score >= 0.4:
                rec.score_band = 'warm'
            else:
                rec.score_band = 'cold'


class AIChatSession(models.Model):
    _name        = 'shopify.ai.chat.session'
    _description = 'AI customer support chat session'
    _order       = 'started_at desc'

    partner_id    = fields.Many2one('res.partner', string='Customer')
    started_at    = fields.Datetime(string='Started', default=fields.Datetime.now)
    ended_at      = fields.Datetime(string='Ended')
    resolved      = fields.Boolean(string='Resolved', default=False)
    escalated     = fields.Boolean(string='Escalated to human', default=False)
    satisfaction  = fields.Integer(string='CSAT score (1–5)')
    transcript    = fields.Text(string='Conversation transcript')
    sale_order_id = fields.Many2one('sale.order', string='Related order')