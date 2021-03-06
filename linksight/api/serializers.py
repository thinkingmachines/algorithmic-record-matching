import csv
import os.path

import magic
from django.contrib.auth import get_user_model
from linksight.api.models import Dataset, Match, MatchItem
from rest_framework import serializers
from rest_framework.authtoken.models import Token


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = get_user_model()
        fields = ('username', 'email', 'first_name', 'last_name')


class TokenSerializer(serializers.ModelSerializer):

    class Meta:
        model = Token
        fields = '__all__'


class DatasetSerializer(serializers.ModelSerializer):

    class Meta:
        model = Dataset
        fields = '__all__'

    def validate_file(self, value):
        mime = magic.from_buffer(value.read(1024), mime=True)
        if mime not in ('text/plain', 'text/csv'):
            raise serializers.ValidationError(
                'LinkSight currently only handles CSV files.',
            )

        row_count = sum(1 for row in csv.reader(map(str, value.open())))
        if row_count > 3000:
            raise serializers.ValidationError(
                'LinkSight can only handle max 3000 rows at the moment.',
            )

        # NOTE: Re-opening the file does `seek(0)`
        return value.open()

    def create(self, validated_data):
        name = os.path.basename(validated_data['file'].name)
        return super().create({
            'name': name,
            'uploader': self.context['uploader'],
            **validated_data,
        })


class DatasetPreviewSerializer(serializers.BaseSerializer):

    def to_representation(self, obj):
        return obj.preview(n=self.context['rows_shown'],
                           match=self.context.get('match'))


class DatasetMatchSerializer(serializers.ModelSerializer):
    export = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = Match
        fields = '__all__'
        read_only_fields = ('dataset',)
        depth = 1

    def create(self, validated_data):
        export = validated_data.pop('export', False)
        obj = super().create(validated_data)
        obj.match_dataset(export=export)
        obj.refresh_from_db()
        return obj


class MatchItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = MatchItem
        exclude = ('match',)


class MatchSaveChoicesSerializer(serializers.BaseSerializer):

    match_choices = serializers.DictField(child=serializers.IntegerField())

    def to_internal_value(self, data):
        return data

    def to_representation(self, obj):
        match = obj.pop('match')
        return {
            'match': match.id,
            'matched_dataset': match.matched_dataset.id,
        }

    def create(self, validated_data):
        match_choices = validated_data['match_choices']
        match = validated_data['match']
        match.save_choices(match_choices)
        match.refresh_from_db()
        match.export()
        return validated_data

