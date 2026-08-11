from extensions import db

from app.models.base import utc_now

class Team(db.Model):
    __tablename__ ='teams'

    id = db.Column(db.Integer , primary_key = True)
    name = db.Column(db.String(100) , nullable = False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=utc_now)


    #relationships
    #ekip üyeleri ve ekibe ait görevelere erişmek için
    members = db.relationship('TeamMember' , back_populates='team' , cascade='all, delete-orphan')
    tasks = db.relationship('Task' , back_populates='team' , cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Team {self.name}'
    
class TeamMember(db.Model):
    __tablename__ = 'team_members'

    id = db.Column(db.Integer , primary_key = True)
    team_id = db.Column(db.Integer , db.ForeignKey('teams.id') , nullable=False)
    user_id = db.Column(db.Integer , db.ForeignKey('users.id') , nullable = False)

    #üyelerin ekip rollerini belirleme
    role = db.Column(db.String(20) , default='Member' , nullable = False)
    joined_at = db.Column(db.DateTime, default=utc_now)

    #relationships
    team = db.relationship('Team', back_populates='members')
    user = db.relationship('User')

    def __repr__(self):
        return f'<TeamMember User : {self.user_id} in Team: {self.team_id}>'
