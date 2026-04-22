import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ShopifyAIRecommendation(models.Model):
    _name = 'shopify.ai.recommendation'
    _description = 'Shopify AI Recommendation'
    _order = 'generated_at desc, id desc'

    customer_id = fields.Many2one('res.partner', string='Customer')
    product_id = fields.Many2one('product.template', string='Product')
    recommendation_type = fields.Char(string='Recommendation Type')
    confidence_score = fields.Float(string='Confidence Score')
    generated_at = fields.Datetime(string='Generated At', default=fields.Datetime.now)
    model_version = fields.Char(string='Model Version')
    accepted = fields.Boolean(string='Accepted', default=False)


class ShopifyAILeadScore(models.Model):
    _name = 'shopify.ai.lead.score'
    _description = 'Shopify AI Lead Score'
    _order = 'evaluated_at desc, id desc'

    customer_id = fields.Many2one('res.partner', string='Customer')
    conversion_probability = fields.Float(string='Conversion Probability')
    features = fields.Text(string='Features')
    evaluated_at = fields.Datetime(string='Evaluated At', default=fields.Datetime.now)
    model_version = fields.Char(string='Model Version')


class ShopifyAIChatSession(models.Model):
    _name = 'shopify.ai.chat.session'
    _description = 'Shopify AI Chat Session'
    _order = 'start_time desc, id desc'

    customer_id = fields.Many2one('res.partner', string='Customer')
    start_time = fields.Datetime(string='Start Time', default=fields.Datetime.now)
    end_time = fields.Datetime(string='End Time')
    resolved = fields.Boolean(string='Resolved', default=False)
    escalated = fields.Boolean(string='Escalated', default=False)
    satisfaction_rating = fields.Integer(string='Satisfaction Rating')
    agent_id = fields.Many2one('res.users', string='Assigned Agent')

    def escalate_to_agent(self, agent_id):
        for session in self:
            agent = self.env['res.users'].browse(agent_id)
            session.write({'escalated': True, 'agent_id': agent.id})
            _logger.info('Chat session %s escalated to agent %s', session.id, agent.name)
